import torch
from cosyvoice.cli.cosyvoice import AutoModel  # noqa: F401

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
print("COSYVOICE_IMPORT_OK")
