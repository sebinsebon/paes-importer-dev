"""Static CI wiring checks; these do not claim remote Actions execution."""
import re
import unittest
import yaml
from support import DEV_ROOT, RUNTIME_ROOT


class WorkflowTests(unittest.TestCase):
    def test_local_publication_stage_requires_explicit_revision_pair(self):
        for root,other in [(DEV_ROOT,'runtime_commit'),(RUNTIME_ROOT,'development_commit')]:
            text=(root/'.github/workflows/ci.yml').read_text(encoding='utf-8')
            document=yaml.load(text,Loader=yaml.BaseLoader)
            self.assertEqual(set(document['on']),{'workflow_dispatch'})
            inputs=document['on']['workflow_dispatch']['inputs']
            self.assertEqual(inputs[other]['required'],'true')
            steps=document['jobs']['checks']['steps']
            for step in steps:
                if 'uses' in step:
                    self.assertRegex(step['uses'],r'@[0-9a-f]{40}$')
            self.assertIn('--runtime runtime',text)
            self.assertIn('--report development/results/ci.json',text)
            self.assertNotIn('playwright install',text)


if __name__=='__main__':unittest.main()
