import importlib.util
from pathlib import Path
import pytest
from asterpdf.core import Document

@pytest.fixture
def document(tmp_path):
    spec=importlib.util.spec_from_file_location('make_demo',Path(__file__).parents[1]/'scripts'/'make_demo.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    filename=mod.create_demo(tmp_path/'sample.pdf')
    doc=Document(filename,tmp_path/'recovery')
    yield doc
    doc.close()
