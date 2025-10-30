#!/bin/bash

# Script para compilar o arquivo .proto e gerar os arquivos Python

echo "Compilando arquivo .proto..."

python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    distributed_printing.proto

if [ $? -eq 0 ]; then
    echo "✓ Compilação concluída com sucesso!"
    echo "Arquivos gerados:"
    echo "  - distributed_printing_pb2.py"
    echo "  - distributed_printing_pb2_grpc.py"
else
    echo "✗ Erro na compilação"
    exit 1
fi
