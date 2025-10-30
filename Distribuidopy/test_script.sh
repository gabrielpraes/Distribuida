#!/bin/bash

# Script para facilitar execução de testes do sistema

echo "======================================"
echo "Sistema de Impressão Distribuída"
echo "======================================"
echo ""

# Função para encerrar todos os processos ao sair
cleanup() {
    echo ""
    echo "Encerrando todos os processos..."
    pkill -P $$
    exit 0
}

trap cleanup SIGINT SIGTERM

# Menu de opções
echo "Escolha uma opção:"
echo "1) Iniciar servidor de impressão"
echo "2) Iniciar cliente"
echo "3) Teste completo (1 servidor + 3 clientes)"
echo "4) Compilar arquivo .proto"
echo "5) Sair"
echo ""
read -p "Opção: " option

case $option in
    1)
        echo ""
        echo "Iniciando servidor de impressão na porta 50051..."
        python printer_server.py
        ;;
    
    2)
        echo ""
        read -p "ID do cliente: " client_id
        read -p "Porta do cliente: " client_port
        read -p "Lista de outros clientes (formato: id:host:port,id:host:port): " clients
        
        echo ""
        echo "Iniciando Cliente $client_id na porta $client_port..."
        python printing_client.py --id $client_id --port $client_port --clients "$clients"
        ;;
    
    3)
        echo ""
        echo "Iniciando teste completo..."
        echo "Pressione Ctrl+C para encerrar todos os processos"
        echo ""
        
        # Inicia servidor de impressão
        echo "→ Iniciando servidor de impressão (porta 50051)..."
        python printer_server.py > logs_server.txt 2>&1 &
        SERVER_PID=$!
        sleep 2
        
        # Inicia Cliente 1
        echo "→ Iniciando Cliente 1 (porta 50052)..."
        python printing_client.py \
            --id 1 \
            --port 50052 \
            --clients "2:localhost:50053,3:localhost:50054" \
            > logs_client1.txt 2>&1 &
        CLIENT1_PID=$!
        sleep 1
        
        # Inicia Cliente 2
        echo "→ Iniciando Cliente 2 (porta 50053)..."
        python printing_client.py \
            --id 2 \
            --port 50053 \
            --clients "1:localhost:50052,3:localhost:50054" \
            > logs_client2.txt 2>&1 &
        CLIENT2_PID=$!
        sleep 1
        
        # Inicia Cliente 3
        echo "→ Iniciando Cliente 3 (porta 50054)..."
        python printing_client.py \
            --id 3 \
            --port 50054 \
            --clients "1:localhost:50052,2:localhost:50053" \
            > logs_client3.txt 2>&1 &
        CLIENT3_PID=$!
        
        echo ""
        echo "======================================"
        echo "Sistema iniciado com sucesso!"
        echo "======================================"
        echo ""
        echo "Processos em execução:"
        echo "  - Servidor: PID $SERVER_PID (porta 50051)"
        echo "  - Cliente 1: PID $CLIENT1_PID (porta 50052)"
        echo "  - Cliente 2: PID $CLIENT2_PID (porta 50053)"
        echo "  - Cliente 3: PID $CLIENT3_PID (porta 50054)"
        echo ""
        echo "Logs salvos em:"
        echo "  - logs_server.txt"
        echo "  - logs_client1.txt"
        echo "  - logs_client2.txt"
        echo "  - logs_client3.txt"
        echo ""
        echo "Acompanhe os logs em tempo real:"
        echo "  tail -f logs_server.txt"
        echo "  tail -f logs_client1.txt"
        echo ""
        echo "Pressione Ctrl+C para encerrar todos os processos"
        
        # Aguarda encerramento
        wait
        ;;
    
    4)
        echo ""
        echo "Compilando arquivo .proto..."
        python -m grpc_tools.protoc \
            -I. \
            --python_out=. \
            --grpc_python_out=. \
            distributed_printing.proto
        
        if [ $? -eq 0 ]; then
            echo "✓ Compilação concluída com sucesso!"
        else
            echo "✗ Erro na compilação"
        fi
        ;;
    
    5)
        echo "Saindo..."
        exit 0
        ;;
    
    *)
        echo "Opção inválida!"
        exit 1
        ;;
esac
