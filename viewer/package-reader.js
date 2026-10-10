/* Bounded ZIP reader. Central directory is checked BEFORE JSZip inflates anything. */
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) module.exports = factory(require("./validator.js"));
  else root.PaessedPackage = factory(root.PaessedValidation);
})(typeof globalThis !== "undefined" ? globalThis : this, function (V) {
  "use strict";
  const { assert, LIMITS } = V;
  const utf8 = new TextDecoder("utf-8", { fatal: true });
  const crcTable = Uint32Array.from({ length: 256 }, (_, n) => {
    for (let i = 0; i < 8; i++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
    return n >>> 0;
  });
  function crc32(bytes) {
    let value = 0xffffffff;
    for (const byte of bytes) value = crcTable[(value ^ byte) & 255] ^ (value >>> 8);
    return (value ^ 0xffffffff) >>> 0;
  }
  function inspectZip(bytes) {
    assert(bytes.byteLength <= LIMITS.archiveBytes && bytes.byteLength >= 22, "ZIP", "tamaño de archivo no permitido");
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const within = (offset, count) => assert(Number.isSafeInteger(offset) && offset >= 0 && offset + count <= bytes.length, "ZIP", "estructura truncada");
    const u16 = offset => { within(offset, 2); return view.getUint16(offset, true); };
    const u32 = offset => { within(offset, 4); return view.getUint32(offset, true); };
    let end = -1;
    for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
      if (u32(i) === 0x06054b50 && i + 22 + u16(i + 20) === bytes.length) { end = i; break; }
    }
    assert(end !== -1, "ZIP", "no se encontró el directorio final");
    assert(u16(end + 4) === 0 && u16(end + 6) === 0, "ZIP", "no se admiten volúmenes múltiples");
    const count = u16(end + 10), size = u32(end + 12), start = u32(end + 16);
    assert(count > 0 && count <= LIMITS.entries && u16(end + 8) === count, "ZIP", "cantidad de entradas inválida (máximo 10.000)");
    assert(size !== 0xffffffff && start !== 0xffffffff && start + size === end, "ZIP", "directorio inválido o ZIP64 no compatible");
    within(start, size);
    let cursor = start, total = 0;
    const entries = new Map(), pathsFolded = new Set(), ranges = [];
    for (let i = 0; i < count; i++) {
      assert(cursor + 46 <= end && u32(cursor) === 0x02014b50, "ZIP", "entrada central inválida");
      const flags = u16(cursor + 8), method = u16(cursor + 10), crc = u32(cursor + 16);
      const compressed = u32(cursor + 20), uncompressed = u32(cursor + 24);
      const nameLength = u16(cursor + 28), extraLength = u16(cursor + 30), commentLength = u16(cursor + 32);
      const offset = u32(cursor + 42), attributes = u32(cursor + 38);
      assert(!(flags & (1 | 32 | 64 | 8192)) && [0, 8].includes(method), "ZIP", "cifrado o compresión no compatible");
      assert(u16(cursor + 34) === 0 && compressed !== 0xffffffff && uncompressed !== 0xffffffff && offset !== 0xffffffff,
        "ZIP", "ZIP64 o volumen múltiple no compatible");
      assert(((attributes >>> 16) & 0xf000) !== 0xa000, "ZIP", "no se admiten enlaces simbólicos");
      const next = cursor + 46 + nameLength + extraLength + commentLength;
      assert(next <= end, "ZIP", "entrada central truncada");
      const name = utf8.decode(bytes.subarray(cursor + 46, cursor + 46 + nameLength));
      const directory = name.endsWith("/");
      V.safePath(name, directory);
      assert(!pathsFolded.has(name.toLowerCase()), "ZIP", `ruta duplicada: ${name}`);
      pathsFolded.add(name.toLowerCase());
      assert(!directory || ((name.startsWith("assets/") || name.startsWith("evidence/")) && uncompressed === 0), "ZIP", `directorio no permitido: ${name}`);
      assert(directory || name === "final.json" || name === "manifest.json" || name.startsWith("assets/") || name.startsWith("evidence/"),
        "ZIP", `archivo no permitido: ${name}`);
      total += uncompressed;
      assert(total <= LIMITS.totalBytes, "ZIP", "supera 256 MiB sin comprimir");
      assert(!name.endsWith(".json") || uncompressed <= LIMITS.jsonBytes, name, "JSON demasiado grande (máximo 24 MiB)");
      assert(offset + 30 <= start && u32(offset) === 0x04034b50, "ZIP", "cabecera local inválida");
      const localNameLength = u16(offset + 26), localExtraLength = u16(offset + 28);
      const dataStart = offset + 30 + localNameLength + localExtraLength;
      assert(dataStart + compressed <= start, "ZIP", "datos fuera del área local");
      const localName = utf8.decode(bytes.subarray(offset + 30, offset + 30 + localNameLength));
      assert(localName === name && u16(offset + 6) === flags && u16(offset + 8) === method, "ZIP", "cabecera local y central no coinciden");
      if (!(flags & 8)) assert(u32(offset + 14) === crc && u32(offset + 18) === compressed && u32(offset + 22) === uncompressed,
        "ZIP", "tamaños/CRC locales no coinciden");
      if (method === 0) assert(compressed === uncompressed, "ZIP", "tamaño STORE inválido");
      ranges.push([offset, dataStart + compressed]);
      entries.set(name, { name, directory, compressed, uncompressed, crc });
      cursor = next;
    }
    assert(cursor === end, "ZIP", "directorio con datos inesperados");
    ranges.sort((a, b) => a[0] - b[0]);
    for (let i = 1; i < ranges.length; i++) assert(ranges[i - 1][1] <= ranges[i][0], "ZIP", "entradas superpuestas");
    assert(entries.has("final.json") && entries.has("manifest.json"), "ZIP", "faltan final.json o manifest.json en la raíz");
    return entries;
  }
  function inflateBounded(file, entry, budget, cancelled) {
    return new Promise((resolve, reject) => {
      let stream, count = 0, stopped = false;
      const chunks = [];
      const stop = error => { if (!stopped) { stopped = true; if (stream) stream.pause(); reject(error); } };
      try {
        stream = file.internalStream("uint8array");
        stream.on("data", chunk => {
          if (stopped) return;
          count += chunk.length; budget.bytes += chunk.length;
          if (cancelled()) return stop(new Error("Importación reemplazada por otra operación"));
          if (count > entry.uncompressed || budget.bytes > LIMITS.totalBytes) return stop(new Error(`${entry.name}: descompresión excede el límite declarado`));
          chunks.push(chunk);
        });
        stream.on("error", stop);
        stream.on("end", () => {
          if (stopped) return;
          try {
            assert(count === entry.uncompressed, entry.name, "tamaño descomprimido inesperado");
            const result = new Uint8Array(count);
            let offset = 0;
            chunks.forEach(chunk => { result.set(chunk, offset); offset += chunk.length; });
            assert(crc32(result) === entry.crc, entry.name, "CRC incorrecto");
            resolve(result);
          } catch (error) { stop(error); }
        });
        stream.resume();
      } catch (error) { stop(error); }
    });
  }
  async function sha256(bytes) {
    assert(globalThis.crypto && globalThis.crypto.subtle, "SHA-256", "WebCrypto no disponible; abra el visor por file:// o localhost en un navegador actualizado");
    const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
  }
  function checkPng(bytes, name) {
    const signature = [137, 80, 78, 71, 13, 10, 26, 10];
    assert(bytes.length >= 33 && signature.every((value, i) => bytes[i] === value), name, "el recurso no es un PNG");
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    assert(view.getUint32(8) === 13 && view.getUint32(12) === 0x49484452, name, "cabecera PNG inválida");
    const width = view.getUint32(16), height = view.getUint32(20);
    assert(width > 0 && height > 0 && width <= 32768 && height <= 32768 && width * height <= 64000000, name, "dimensiones PNG fuera de límite");
  }
  async function readPackage(input, options = {}) {
    const JSZip = options.JSZip || globalThis.JSZip;
    assert(JSZip, "Visor", "JSZip local no está disponible");
    const cancelled = options.cancelled || (() => false);
    let bytes;
    if (typeof Blob !== "undefined" && input instanceof Blob) {
      assert(input.size <= LIMITS.archiveBytes, "ZIP", "archivo demasiado grande (máximo 272 MiB)");
      bytes = new Uint8Array(await input.arrayBuffer());
    } else if (input instanceof ArrayBuffer) bytes = new Uint8Array(input);
    else if (ArrayBuffer.isView(input)) bytes = new Uint8Array(input.buffer, input.byteOffset, input.byteLength);
    else throw new Error("Se esperaba un File, Blob, ArrayBuffer o Uint8Array");
    if (cancelled()) throw new Error("Importación cancelada");
    const entries = inspectZip(bytes);
    const zip = await JSZip.loadAsync(bytes, { checkCRC32: false, createFolders: false });
    assert(Object.keys(zip.files).length === entries.size, "ZIP", "JSZip alteró el inventario");
    entries.forEach((entry, path) => {
      const file = zip.files[path];
      assert(file && file.dir === entry.directory, "ZIP", `ruta normalizada o ausente: ${path}`);
      if (file.unsafeOriginalName !== undefined) {
        V.safePath(file.unsafeOriginalName, file.dir);
        assert(file.unsafeOriginalName === path, "ZIP", "nombre original alterado");
      }
      assert(file.name === path, "ZIP", "nombre normalizado inesperado");
    });
    const budget = { bytes: 0 };
    const read = name => inflateBounded(zip.files[name], entries.get(name), budget, cancelled);
    const manifestBytes = await read("manifest.json");
    const finalBytes = await read("final.json");
    function json(value, name) {
      try { return JSON.parse(utf8.decode(value)); } catch (_) { throw new Error(`${name}: JSON o UTF-8 inválido`); }
    }
    const manifest = json(manifestBytes, "manifest.json");
    const data = json(finalBytes, "final.json");
    const validation = V.validateFinal(data);
    const fileSizes = new Map([...entries].filter(([, entry]) => !entry.directory).map(([path, entry]) => [path, entry.uncompressed]));
    const listed = V.validateManifest(manifest, fileSizes, data, validation);
    assert(await sha256(finalBytes) === listed.get("final.json").sha256.toLowerCase(), "final.json", "SHA-256 incorrecto");
    const blobs = new Map();
    for (const resource of validation.resources.values()) {
      if (cancelled()) throw new Error("Importación cancelada");
      const content = await read(resource.path);
      assert(await sha256(content) === resource.sha256.toLowerCase(), resource.path, "SHA-256 incorrecto");
      checkPng(content, resource.path);
      blobs.set(resource.id, new Blob([content], { type: "image/png" }));
    }
    if (cancelled()) throw new Error("Importación cancelada");
    return { data, validation, blobs, manifest, compressedBytes: bytes.length, uncompressedBytes: budget.bytes };
  }
  return Object.freeze({ inspectZip, readPackage, sha256, crc32, checkPng });
});
