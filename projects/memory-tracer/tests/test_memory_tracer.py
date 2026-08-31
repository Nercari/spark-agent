import unittest
import os
import tempfile
import shutil
from platform.memory.contracts import MemoryScope, MemoryKind, MemoryStatus
from platform.memory.backend import LocalFilesystemMemoryBackend
from platform.memory.store import MemoryStore
from projects.memory_tracer.src.tracer import run_memory_tracer


class TestMemoryTracer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="spark_mem_tracer_")
        self.backend = LocalFilesystemMemoryBackend(base_dir=self.test_dir)
        self.store = MemoryStore(backend=self.backend)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_tracer_workflow(self):
        ok, msg, rec = self.store.create_or_update_memory(
            scope=MemoryScope.PROJECT,
            scope_id="proj_trace",
            kind=MemoryKind.FACT,
            key="trace_k",
            value="trace_v",
        )
        self.assertTrue(ok)
        self.assertIsNotNone(rec)


if __name__ == "__main__":
    unittest.main()
