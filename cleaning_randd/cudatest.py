import torch
print(torch.__version__)
if torch.cuda.is_available():
    print("CUDA est disponible sur cet ordinateur.")
else:
    print("CUDA n'est pas disponible sur cet ordinateur.")