/* Contract validation shared by the offline browser and Node regression tests. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PaessedValidation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const VERSION = "0.1.0";
  const LIMITS = Object.freeze({ totalBytes: 256 * 1024 * 1024, archiveBytes: 272 * 1024 * 1024,
    entries: 10000, jsonBytes: 24 * 1024 * 1024, blocks: 100000, depth: 16, string: 1000000 });
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  function fail(where, message) { throw new Error(`${where}: ${message}`); }
  function assert(condition, where, message) { if (!condition) fail(where, message); }
  function object(value, where, keys = [], additional = true) {
    assert(value !== null && typeof value === "object" && !Array.isArray(value), where, "se esperaba un objeto");
    keys.forEach(key => assert(own(value, key), where, `falta ${key}`));
    if (!additional) Object.keys(value).forEach(key => assert(keys.includes(key), where, `campo no permitido: ${key}`));
    return value;
  }
  function array(value, where) { assert(Array.isArray(value), where, "se esperaba una lista"); return value; }
  function string(value, where, nonempty = false) {
    assert(typeof value === "string" && value.length <= LIMITS.string && (!nonempty || value.length > 0),
      where, "texto ausente, vacío o demasiado largo"); return value;
  }
  function nullable(value, where) { if (value !== null) string(value, where); }
  function integer(value, where, minimum = 0) {
    assert(Number.isSafeInteger(value) && value >= minimum, where, `se esperaba un entero ≥ ${minimum}`);
  }
  function member(value, choices, where) { assert(choices.includes(value), where, `valor inválido (${choices.join(" / ")})`); }
  function hash(value, where) { assert(typeof value === "string" && /^[a-f0-9]{64}$/.test(value), where, "SHA-256 inválido"); }
  function safePath(value, directory = false) {
    string(value, "Ruta", true);
    assert(value.length <= 1024 && !/[\\:\u0000-\u001f\u007f]/.test(value) && !value.startsWith("/"), "Ruta", `ruta insegura: ${value}`);
    const path = directory && value.endsWith("/") ? value.slice(0, -1) : value;
    assert(path.split("/").every(part => part && part !== "." && part !== ".." && !/[. ]$/.test(part) &&
      !/[<>"|?*]/.test(part) && !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part)), "Ruta", `ruta insegura: ${value}`);
    return value;
  }
  function bbox(value, where) {
    assert(Array.isArray(value) && value.length === 4 && value.every(v => Number.isFinite(v) && v >= 0) &&
      value[2] > value[0] && value[3] > value[1], where, "bbox debe ser [x0,y0,x1,y1], finito y de área positiva");
  }
  function unique(items, where) {
    const map = new Map();
    items.forEach((item, i) => {
      object(item, `${where}[${i}]`, ["id"]);
      string(item.id, `${where}[${i}].id`, true);
      assert(!map.has(item.id), where, `ID duplicado: ${item.id}`);
      map.set(item.id, item);
    });
    return map;
  }
  function validateFinal(data) {
    object(data, "final.json", ["format", "schema_version", "pipeline", "run", "exam", "sources", "questions", "assets", "evidence"], false);
    assert(data.format === "paessed-benchmark", "format", "no es un benchmark PAESSED");
    assert(data.schema_version === VERSION, "schema_version", `versión no compatible; se requiere ${VERSION}`);
    member(data.pipeline, ["hybrid", "pdf-direct", "demo"], "pipeline");
    object(data.run, "run", ["id", "cli", "model", "created_at"]);
    ["id", "cli", "model", "created_at"].forEach(key => string(data.run[key], `run.${key}`, key === "id"));
    // run is extensible; variant and protocol are producer metadata, not audit results.
    if (own(data.run, "input_mode")) string(data.run.input_mode, "run.input_mode");
    ["suite_sha256", "config_hash"].forEach(key => { if (own(data.run, key)) hash(data.run[key], `run.${key}`); });
    if (own(data.run, "all_pages_read")) assert(typeof data.run.all_pages_read === "boolean", "run.all_pages_read", "debe ser booleano");
    object(data.exam, "exam", ["id", "title", "scope", "expected_questions"], false);
    string(data.exam.id, "exam.id", true); string(data.exam.title, "exam.title", true);
    member(data.exam.scope, ["sample", "full", "demo"], "exam.scope");
    const sources = unique(array(data.sources, "sources"), "sources");
    assert(sources.size > 0, "sources", "se requiere al menos una fuente");
    sources.forEach(source => {
      object(source, `Fuente ${source.id}`, ["id", "name", "sha256", "page_count", "role"], false);
      string(source.name, "source.name", true); hash(source.sha256, "source.sha256");
      integer(source.page_count, "source.page_count", 1); member(source.role, ["exam", "solution"], "source.role");
    });
    const page = (sourceId, pageNumber, where) => {
      assert(sources.has(sourceId), where, `fuente desconocida: ${sourceId}`);
      integer(pageNumber, where, 1);
      assert(pageNumber <= sources.get(sourceId).page_count, where, "página fuera de la fuente");
    };
    const resources = new Map();
    const paths = new Set();
    ["assets", "evidence"].forEach(collection => {
      unique(array(data[collection], collection), collection).forEach(resource => {
        object(resource, `${collection}.${resource.id}`, ["id", "path", "sha256", "mime", "source_id", "page", "bbox"], false);
        assert(!resources.has(resource.id), collection, `ID de recurso duplicado: ${resource.id}`);
        safePath(resource.path);
        assert(resource.path.startsWith(`${collection}/`), collection, `el recurso debe estar bajo ${collection}/`);
        assert(resource.path.endsWith(".png"), collection, "el recurso debe usar la extensión .png");
        assert(!paths.has(resource.path.toLowerCase()), collection, `ruta de recurso duplicada: ${resource.path}`);
        paths.add(resource.path.toLowerCase()); hash(resource.sha256, "resource.sha256");
        assert(resource.mime === "image/png", "resource.mime", "solo se admite image/png");
        page(resource.source_id, resource.page, resource.id); bbox(resource.bbox, `${resource.id}.bbox`);
        resources.set(resource.id, resource);
      });
    });
    const assets = new Map(data.assets.map(asset => [asset.id, asset]));
    let blockCount = 0;
    let unresolved = 0;
    function blocks(values, where, sourceId, depth = 0) {
      assert(depth <= LIMITS.depth, where, "bloques demasiado anidados");
      array(values, where).forEach((block, i) => {
        assert(++blockCount <= LIMITS.blocks, where, "demasiados bloques");
        const at = `${where}[${i}]`;
        object(block, at, ["type"]);
        switch (block.type) {
          case "text":
            object(block, at, ["type", "text"], false); string(block.text, `${at}.text`, true); break;
          case "math":
            object(block, at, ["type", "latex", "display"], false);
            string(block.latex, `${at}.latex`, true);
            assert(!block.latex.startsWith("$") && !block.latex.endsWith("$"), at, "LaTeX debe ir sin delimitadores $");
            assert(block.latex.length <= 20000, at, "fórmula demasiado larga");
            assert(typeof block.display === "boolean", at, "display debe ser booleano"); break;
          case "image":
            object(block, at, ["type", "asset_id", "alt"], false);
            assert(assets.has(block.asset_id), at, `asset_id desconocido: ${block.asset_id}`);
            assert(assets.get(block.asset_id).source_id === sourceId, at, "imagen de una fuente distinta de la pregunta");
            string(block.alt, `${at}.alt`); break;
          case "table":
            object(block, at, ["type", "rows"], false);
            assert(array(block.rows, `${at}.rows`).length > 0, at, "tabla vacía");
            let columns = null;
            array(block.rows, `${at}.rows`).forEach((row, rowIndex) => {
              array(row, `${at}.rows[${rowIndex}]`);
              if (columns === null) columns = row.length;
              assert(row.length > 0 && row.length === columns, at, "tabla vacía o no rectangular");
              row.forEach((cell, column) => blocks(cell, `${at}.cell[${rowIndex},${column}]`, sourceId, depth + 1));
            }); break;
          case "unresolved":
            object(block, at, ["type", "reason"], false); string(block.reason, `${at}.reason`, true); unresolved++; break;
          default: fail(at, `tipo de bloque desconocido: ${block.type}`);
        }
      });
    }
    const expected = unique(array(data.exam.expected_questions, "exam.expected_questions"), "expected_questions");
    assert(expected.size > 0, "expected_questions", "la selección no puede estar vacía");
    const sourceNumbers = new Set();
    expected.forEach(question => {
      object(question, "expected_question", ["id", "source_id", "number"], false);
      assert(sources.has(question.source_id), question.id, "fuente esperada desconocida");
      string(question.number, `${question.id}.number`, true);
      const key = JSON.stringify([question.source_id, question.number]);
      assert(!sourceNumbers.has(key), question.id, "número duplicado en la misma fuente"); sourceNumbers.add(key);
    });
    const questions = unique(array(data.questions, "questions"), "questions");
    assert(questions.size === expected.size && [...expected.keys()].every(id => questions.has(id)), "questions", "cobertura distinta de expected_questions; use unresolved para faltantes");
    const counts = { missing: 0, provisional: 0, verified: 0, pending: 0, reviewed: 0, rejected: 0 };
    questions.forEach(question => {
      const at = `Pregunta ${question.id}`;
      object(question, at, ["id", "source_id", "number", "regions", "stem", "options", "answer", "explanation", "fidelity", "issues"], false);
      const match = expected.get(question.id);
      assert(match && question.source_id === match.source_id && question.number === match.number, at, "fuente/número no coincide con la selección");
      assert(sources.get(question.source_id).role === "exam", at, "la pregunta debe pertenecer a una fuente exam");
      array(question.regions, `${at}.regions`).forEach(region => {
        object(region, `${at}.region`, ["page", "bbox"], false);
        page(question.source_id, region.page, at); bbox(region.bbox, `${at}.region.bbox`);
      });
      const unresolvedBefore = unresolved;
      assert(array(question.stem, `${at}.stem`).length > 0, at, "enunciado vacío; use unresolved");
      blocks(question.stem, `${at}.stem`, question.source_id);
      const labels = new Set();
      array(question.options, `${at}.options`).forEach(option => {
        object(option, `${at}.option`, ["label", "blocks"], false); string(option.label, `${at}.option.label`, true);
        assert(/^[A-Z]$/.test(option.label), at, "la alternativa debe ser una letra A–Z");
        assert(!labels.has(option.label), at, `alternativa duplicada: ${option.label}`); labels.add(option.label);
        assert(array(option.blocks, `${at}.option.blocks`).length > 0, at, "alternativa sin contenido");
        blocks(option.blocks, `${at}.option.${option.label}`, question.source_id);
      });
      object(question.answer, `${at}.answer`, ["label", "status", "origin", "source_ref"], false);
      member(question.answer.status, ["missing", "provisional", "verified"], `${at}.answer.status`);
      member(question.answer.origin, ["none", "model", "answer-key"], `${at}.answer.origin`);
      nullable(question.answer.source_ref, `${at}.answer.source_ref`);
      assert(question.answer.label === null || labels.has(question.answer.label), at, "la respuesta no referencia una alternativa");
      assert(question.answer.status === "missing" ? question.answer.label === null : question.answer.label !== null,
        at, "estado de respuesta incompatible con label");
      assert((question.answer.origin === "none") === (question.answer.status === "missing"), at, "origen y estado de respuesta incompatibles");
      object(question.explanation, `${at}.explanation`, ["blocks", "status"], false);
      member(question.explanation.status, ["missing", "provisional", "verified"], `${at}.explanation.status`);
      blocks(question.explanation.blocks, `${at}.explanation.blocks`, question.source_id);
      assert((question.explanation.status === "missing") === (question.explanation.blocks.length === 0), at, "estado de explicación incompatible con su contenido");
      object(question.fidelity, `${at}.fidelity`, ["status", "review_ref"], false);
      member(question.fidelity.status, ["pending", "reviewed", "rejected"], `${at}.fidelity.status`);
      nullable(question.fidelity.review_ref, `${at}.fidelity.review_ref`);
      const hasUnresolved = unresolved > unresolvedBefore;
      assert((labels.size >= 2 && question.regions.length > 0) || hasUnresolved, at, "se requieren región y dos alternativas, o un bloque unresolved");
      assert(question.fidelity.status !== "reviewed" || (!hasUnresolved && Boolean(question.fidelity.review_ref)), at, "fidelidad revisada requiere referencia y contenido resuelto");
      assert(question.answer.status !== "verified" || (Boolean(question.answer.source_ref) && question.fidelity.status === "reviewed"), at, "respuesta confirmada requiere referencia y fidelidad revisada");
      assert(question.explanation.status !== "verified" || question.answer.status === "verified", at, "explicación confirmada requiere respuesta confirmada");
      array(question.issues, `${at}.issues`).forEach(issue => string(issue, `${at}.issues`));
      counts[question.answer.status]++; counts[question.fidelity.status]++;
    });
    return { sources, resources, assets, questions, expected, counts, unresolved, blockCount };
  }
  function validateManifest(manifest, fileSizes, data, validation) {
    object(manifest, "manifest.json", ["format", "schema_version", "files"]);
    assert(manifest.format === "paessed-package" && manifest.schema_version === VERSION,
      "manifest.json", "formato o versión no compatible");
    const listed = new Map();
    array(manifest.files, "manifest.files").forEach(entry => {
      object(entry, "manifest.files[]", ["path", "sha256", "bytes"]);
      safePath(entry.path); hash(entry.sha256, "manifest.sha256"); integer(entry.bytes, "manifest.bytes");
      assert(entry.path !== "manifest.json" && !listed.has(entry.path), "manifest", `entrada duplicada o autorreferencia: ${entry.path}`);
      listed.set(entry.path, entry);
    });
    const required = new Set(["final.json", ...validation.resources.values()].map(value => typeof value === "string" ? value : value.path));
    assert(listed.size === required.size && [...required].every(path => listed.has(path)), "manifest", "el inventario debe contener exactamente final.json y los recursos declarados");
    assert(fileSizes.size === listed.size + 1 && fileSizes.has("manifest.json") && [...listed.keys()].every(path => fileSizes.has(path)),
      "ZIP", "el inventario real no coincide con manifest.json");
    listed.forEach(entry => assert(fileSizes.get(entry.path) === entry.bytes, entry.path, "tamaño distinto del manifiesto"));
    validation.resources.forEach(resource => assert(listed.get(resource.path).sha256.toLowerCase() === resource.sha256.toLowerCase(),
      resource.path, "hash de recurso distinto del manifiesto"));
    return listed;
  }
  return Object.freeze({ VERSION, LIMITS, assert, safePath, validateFinal, validateManifest });
});
