"""Native checks of reviewed frozen roots; never constructs an import or database."""
from pathlib import Path
import hashlib,json,os,re,unittest
from decision_tracker import legacy_encoding as encoding
from decision_tracker.errors import Fault

ROOT=Path('/input') if Path('/input/input-manifest.json').is_file() else Path.cwd()

class FrozenInputChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((ROOT/'input-manifest.json').read_text(encoding='utf-8'))
        cls.inputs={}
        for row in cls.manifest['files']:
            path=ROOT/row['copy_path'];raw=path.read_bytes()
            assert hashlib.sha256(raw).hexdigest()==row['sha256'] and len(raw)==row['bytes']
            cls.inputs[row['project']]=json.loads(raw)

    def test_production_encoder_numeric_tokens_and_unknowns(self):
        raw='{"z":[2,1],"num":1.2300,"exp":1E+02,"zero":-0,"null":null,"empty":"","unicode":"🧭"}'
        value=encoding.parse(raw);out=encoding.e1(value)
        for token in ('1.2300','1E+02','-0'):self.assertIn(token,out)
        self.assertEqual(value['z'],['2','1']);self.assertEqual(encoding.literal_type(value['num']),'number')
        self.assertIsNone(value['null']);self.assertEqual(value['empty'],'');self.assertNotIn('absent',value)
        for invalid in ('{"x":1,"x":2}','NaN','"\\ud800"'):
            with self.assertRaises(Fault):encoding.parse(invalid)

    def test_every_selected_payload_type_hash_length_and_roundtrip(self):
        for namespace,doc in self.inputs.items():
            with self.subTest(namespace=namespace):
                for row in doc['literal_payload_rows']:
                    raw=row['value_json'];value=encoding.parse(raw)
                    self.assertEqual(encoding.e1(value),raw)
                    self.assertEqual(encoding.digest(value),row['payload_sha256'])
                    self.assertEqual(encoding.literal_type(value),row['literal_type'])
                    self.assertEqual(len(raw.encode('utf-8')),row['encoded_bytes'])
                    # A read chunk may split Unicode bytes; recombine before decoding.
                    parts=[raw.encode('utf-8')[n:n+127] for n in range(0,len(raw.encode('utf-8')),127)]
                    self.assertEqual(b''.join(parts).decode('utf-8'),raw)

    def test_all_roots_and_original_identity_recipes(self):
        for namespace,doc in self.inputs.items():
            versions={v['version_id']:v for v in doc['versions']}
            payloads={v['payload_sha256']:v for v in doc['literal_payload_rows']}
            self.assertEqual(len(versions),len(doc['versions']))
            self.assertEqual(len(payloads),len(doc['literal_payload_rows']))
            members=set();selectors={key:set() for key in versions}
            for v in versions.values():
                self.assertEqual(v['namespace'],namespace)
                self.assertEqual(v['version_id'],encoding.digest(['legacy-version/v1',namespace,v['locator'],v['file_sha256']]))
            for m in doc['selected_members']:
                self.assertNotIn(m['member_id'],members);members.add(m['member_id'])
                self.assertIn(m['payload_sha256'],payloads);self.assertIn(m['version_id'],versions)
                self.assertEqual(m['member_id'],encoding.digest(['legacy-member/v1',m['version_id'],m['selector']]))
                selectors[m['version_id']].add(m['selector'])
                self.assertEqual(m['literal_type'],payloads[m['payload_sha256']]['literal_type'])
                self.assertGreaterEqual(m['source_order'],0)
            for v in versions.values():self.assertEqual(selectors[v['version_id']],set(v['selector_roots']))

    def test_qa_snapshot_event_order_and_incident_context(self):
        doc=self.inputs['qa-engine'];payloads={v['payload_sha256']:v for v in doc['literal_payload_rows']}
        events=[];versions=set();context=0
        for m in doc['selected_members']:
            versions.add(m['version_id'])
            if m['selector'].startswith('/events/'):
                events.append(encoding.parse(payloads[m['payload_sha256']]['value_json']))
            if not m['association_source_ids']:context+=1
        self.assertEqual(len(versions),17);self.assertTrue(events);self.assertGreater(context,0)
        for event in events:
            self.assertIn('record_id',event);self.assertIn('old_value',event);self.assertIn('new_value',event)
            self.assertIn('authority_ref',event)
        self.assertEqual(len(doc['selected_members']),1210)

    def test_ledger_git_parent_objects_and_project_context(self):
        doc=self.inputs['polymath-ledger'];payloads={v['payload_sha256']:v for v in doc['literal_payload_rows']}
        versions={v['version_id']:v for v in doc['versions']};commits={};context=0
        for m in doc['selected_members']:
            if not m['association_source_ids']:context+=1
        for row in doc['git_commit_objects']:
            raw=row['source_commit_object'].encode('utf-8');object_id=row['commit']
            self.assertEqual(hashlib.sha256(raw).hexdigest(),row['sha256'])
            self.assertEqual(hashlib.sha1(b'commit '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),object_id)
            self.assertNotIn(object_id,commits)
            commits[object_id]=re.findall(r'^parent ([0-9a-f]{40})$',row['source_commit_object'],re.M)
        self.assertEqual(len(commits),85);self.assertGreater(context,0)
        # External parents are retained boundary references, not invented missing nodes.
        def visit(key,stack):
            self.assertNotIn(key,stack)
            for parent in commits.get(key,[]):visit(parent,stack|{key})
        for key in commits:visit(key,set())
        hashes={v['file_sha256'] for v in versions.values()}
        boundaries={b['source_sha256']:b for b in doc['unselected_version_boundaries']}
        for appearance in [*doc['source_appearances'],*doc['index_appearances']]:
            if 'source_sha256' in appearance:
                digest=appearance['source_sha256']
                if digest not in hashes:
                    self.assertIn(digest,boundaries)
                    boundary=boundaries[digest]
                    self.assertEqual(boundary['commit'],appearance['commit'])
                    self.assertEqual(boundary['selected_sections'],{s:'absent' for s in ('decision-index','decision-impacts','deprecated-decisions')})
            self.assertIn(appearance['commit'],commits)
        self.assertEqual(len(boundaries),1)
        self.assertEqual(len(doc['selected_members']),4659)

    def test_bound_copy_inventory_and_source_read_only(self):
        self.assertEqual(set(self.inputs),{'qa-engine','polymath-ledger'})
        self.assertEqual(sum(len(d['selected_members']) for d in self.inputs.values()),5869)
        self.assertEqual(sum(len(d['versions']) for d in self.inputs.values()),176)
        # Actual OS denial; no convention substitutes for input mount protection.
        if ROOT==Path('/input'):
            with self.assertRaises(OSError):(ROOT/'forbidden-write').write_text('test')
        schema=ROOT/'src/decision_tracker/schemas/legacy-import-v1.json'
        self.assertEqual(hashlib.sha256(schema.read_bytes()).hexdigest(),self.manifest['contract_sha256'])

if __name__=='__main__':unittest.main(verbosity=2)
