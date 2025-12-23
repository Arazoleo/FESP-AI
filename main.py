#!/usr/bin/env python3
import warnings
import os

# Suprimir warnings ANTES de importar qualquer coisa
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

# Importar urllib3 e desabilitar warnings específicos
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.NotOpenSSLWarning)
except ImportError:
    pass

from src.cli import main

if __name__ == "__main__":
    main()

