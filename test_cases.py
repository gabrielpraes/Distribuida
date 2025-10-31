"""
Testes automatizados para o sistema de impressão distribuída
"""
import unittest
import threading
import time
from lamport_clock import LamportClock
import grpc
from concurrent import futures

import distributed_printing_pb2
import distributed_printing_pb2_grpc
from printing_client import PrintingClient, MutexState


class TestLamportClock(unittest.TestCase):
    """Testes para o Relógio de Lamport"""
    
    def test_initialization(self):
        """Testa inicialização do relógio"""
        clock = LamportClock()
        self.assertEqual(clock.get_time(), 0)
    
    def test_tick(self):
        """Testa incremento do relógio"""
        clock = LamportClock()
        
        time1 = clock.tick()
        self.assertEqual(time1, 1)
        
        time2 = clock.tick()
        self.assertEqual(time2, 2)
        
        time3 = clock.tick()
        self.assertEqual(time3, 3)
    
    def test_update_with_higher_timestamp(self):
        """Testa atualização com timestamp maior"""
        clock = LamportClock()
        clock.tick()  # time = 1
        clock.tick()  # time = 2
        
        # Recebe timestamp 10
        new_time = clock.update(10)
        self.assertEqual(new_time, 11)  # max(2, 10) + 1
        
        # Próximo tick deve ser 12
        next_time = clock.tick()
        self.assertEqual(next_time, 12)
    
    def test_update_with_lower_timestamp(self):
        """Testa atualização com timestamp menor"""
        clock = LamportClock()
        for _ in range(5):
            clock.tick()  # time = 5
        
        # Recebe timestamp 2 (menor que atual)
        new_time = clock.update(2)
        self.assertEqual(new_time, 6)  # max(5, 2) + 1
    
    def test_update_with_equal_timestamp(self):
        """Testa atualização com timestamp igual"""
        clock = LamportClock()
        for _ in range(5):
            clock.tick()  # time = 5
        
        # Recebe timestamp 5 (igual ao atual)
        new_time = clock.update(5)
        self.assertEqual(new_time, 6)  # max(5, 5) + 1
    
    def test_thread_safety(self):
        """Testa thread safety do relógio"""
        clock = LamportClock()
        results = []
        errors = []
        
        def tick_multiple_times(n):
            try:
                for _ in range(n):
                    t = clock.tick()
                    results.append(t)
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)
        
        # Cria múltiplas threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=tick_multiple_times, args=(20,))
            threads.append(t)
            t.start()
        
        # Aguarda conclusão
        for t in threads:
            t.join()
        
        # Verifica se não houve erros
        self.assertEqual(len(errors), 0)
        
        # Verifica se todos os valores são únicos e crescentes
        results.sort()
        self.assertEqual(len(results), 100)  # 5 threads * 20 ticks
        self.assertEqual(results[-1], 100)   # Último valor deve ser 100
    
    def test_concurrent_updates(self):
        """Testa atualizações concorrentes"""
        clock = LamportClock()
        results = []
        
        def update_with_random_timestamp(ts):
            new_time = clock.update(ts)
            results.append(new_time)
        
        # Cria threads com diferentes timestamps
        threads = []
        timestamps = [5, 10, 3, 15, 7, 12, 20, 1, 18, 9]
        
        for ts in timestamps:
            t = threading.Thread(target=update_with_random_timestamp, args=(ts,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Todos os valores devem ser maiores que 0
        self.assertTrue(all(r > 0 for r in results))
        
        # Valor final deve ser maior que todos os timestamps recebidos
        final_time = clock.get_time()
        self.assertGreaterEqual(final_time, max(timestamps))


class TestMutexLogic(unittest.TestCase):
    """Testes para lógica de exclusão mútua"""
    
    def test_priority_by_timestamp(self):
        """Testa prioridade por timestamp"""
        # Menor timestamp tem prioridade
        self.assertTrue(self._has_priority(5, 1, 10, 2))
        self.assertFalse(self._has_priority(10, 1, 5, 2))
    
    def test_priority_by_id(self):
        """Testa desempate por ID quando timestamps iguais"""
        # Timestamps iguais, menor ID ganha
        self.assertTrue(self._has_priority(5, 1, 5, 2))
        self.assertFalse(self._has_priority(5, 2, 5, 1))
    
    def test_priority_edge_cases(self):
        """Testa casos extremos"""
        # Timestamp muito diferente
        self.assertTrue(self._has_priority(1, 999, 1000, 1))
        
        # IDs iguais (não deveria acontecer, mas testa)
        self.assertFalse(self._has_priority(5, 1, 5, 1))
    
    def _has_priority(self, my_ts, my_id, other_ts, other_id):
        """Implementa lógica de prioridade"""
        if my_ts < other_ts:
            return True
        elif my_ts == other_ts:
            return my_id < other_id
        else:
            return False


class TestCausalOrdering(unittest.TestCase):
    """Testes para ordenação causal de eventos"""
    
    def test_local_events_ordering(self):
        """Testa ordenação de eventos locais"""
        clock = LamportClock()
        
        events = []
        for i in range(10):
            ts = clock.tick()
            events.append(('local', i, ts))
        
        # Verifica se timestamps são crescentes
        timestamps = [e[2] for e in events]
        self.assertEqual(timestamps, sorted(timestamps))
    
    def test_message_ordering(self):
        """Testa ordenação entre mensagens"""
        clock1 = LamportClock()
        clock2 = LamportClock()
        
        # Processo 1 envia mensagem
        ts1 = clock1.tick()
        
        # Processo 2 recebe e responde
        clock2.update(ts1)
        ts2 = clock2.tick()
        
        # Processo 1 recebe resposta
        clock1.update(ts2)
        ts3 = clock1.tick()
        
        # Verifica ordenação causal
        self.assertLess(ts1, ts2)
        self.assertLess(ts2, ts3)
    
    def test_concurrent_events(self):
        """Testa eventos concorrentes"""
        clock1 = LamportClock()
        clock2 = LamportClock()
        
        # Eventos concorrentes (sem comunicação)
        ts1 = clock1.tick()
        ts2 = clock2.tick()
        
        # Não há relação causal, mas timestamps podem ser comparados
        # para desempate
        self.assertIsNotNone(ts1)
        self.assertIsNotNone(ts2)


class TestSystemIntegration(unittest.TestCase):
    """Testes de integração do sistema"""
    
    def test_request_sequence(self):
        """Testa sequência de requisição"""
        # Simula fluxo de requisição
        clock = LamportClock()
        
        # 1. Cliente inicia requisição
        request_ts = clock.tick()
        self.assertEqual(request_ts, 1)
        
        # 2. Recebe respostas de outros
        for other_ts in [2, 3, 4]:
            clock.update(other_ts)
        
        # 3. Entra na seção crítica
        enter_ts = clock.tick()
        self.assertGreater(enter_ts, max([2, 3, 4]))
        
        # 4. Sai da seção crítica
        exit_ts = clock.tick()
        self.assertGreater(exit_ts, enter_ts)
    
    def test_multiple_clients_ordering(self):
        """Testa ordenação com múltiplos clientes"""
        clocks = [LamportClock() for _ in range(3)]
        requests = []
        
        # Cada cliente faz uma requisição
        for i, clock in enumerate(clocks):
            ts = clock.tick()
            requests.append((i, ts))
        
        # Ordena por timestamp (e ID para desempate)
        requests.sort(key=lambda x: (x[1], x[0]))
        
        # Primeiro da fila deve ter menor timestamp
        first_client, first_ts = requests[0]
        for client, ts in requests[1:]:
            self.assertGreaterEqual(ts, first_ts)


def run_tests():
    """Executa todos os testes"""
    print("="*60)
    print("EXECUTANDO TESTES DO SISTEMA")
    print("="*60)
    print()
    
    # Cria suite de testes
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Adiciona testes
    suite.addTests(loader.loadTestsFromTestCase(TestLamportClock))
    suite.addTests(loader.loadTestsFromTestCase(TestMutexLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestCausalOrdering))
    suite.addTests(loader.loadTestsFromTestCase(TestSystemIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestDistributedPrintingIntegration))
    
    # Executa testes
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Resumo
    print()
    print("="*60)
    print("RESUMO DOS TESTES")
    print("="*60)
    print(f"Total de testes: {result.testsRun}")
    print(f"Sucessos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Falhas: {len(result.failures)}")
    print(f"Erros: {len(result.errors)}")
    print("="*60)
    
    return result.wasSuccessful()


class TestDistributedPrintingIntegration(unittest.TestCase):
    """Testes de integração para os cenários descritos pelo usuário
    Cenário 1: Funcionamento Básico sem Concorrência
    Cenário 2: Concorrência entre clientes A e B enquanto C está usando
    """

    def setUp(self):
        # Criar um servicer de impressão de teste que registra a sequência de impressões
        self.printed_sequence = []

        class TestPrinterServicer(distributed_printing_pb2_grpc.PrintingServiceServicer):
            def __init__(self, outer_list):
                self.outer = outer_list
                self.print_count = 0

            def SendToPrinter(self, request, context):
                # Registrar chamada (client_id, timestamp, message)
                self.print_count += 1
                self.outer.append((request.client_id, request.lamport_timestamp, request.message_content))
                return distributed_printing_pb2.PrintResponse(
                    success=True,
                    confirmation_message=f"Printed #{self.print_count}",
                    lamport_timestamp=request.lamport_timestamp
                )

        # Inicia servidor de impressão de teste em 50051
        self.printer_servicer = TestPrinterServicer(self.printed_sequence)
        self.printer_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        distributed_printing_pb2_grpc.add_PrintingServiceServicer_to_server(
            self.printer_servicer, self.printer_server
        )
        self.printer_server.add_insecure_port('[::]:50051')
        self.printer_server.start()

        # Lista para manter referências dos clientes criados e encerrá-los no tearDown
        self.clients = []

        # Pequena pausa para garantir que o servidor esteja pronto
        time.sleep(0.2)

    def tearDown(self):
        # Parar servidor de impressão
        try:
            self.printer_server.stop(0)
        except Exception:
            pass

        # Encerrar clientes criados
        for c in self.clients:
            try:
                c.shutdown()
            except Exception:
                pass

    def _create_clients(self, client_defs):
        """Helper que cria, inicia servidores e conecta clientes.

        client_defs: lista de tuples (client_id, port)
        Retorna dict id->client
        """
        # Monta peer addresses para cada cliente
        peers = {cid: f'localhost:{port}' for (cid, port) in client_defs}

        clients = {}
        for cid, port in client_defs:
            # peers less self
            peer_map = {k: v for k, v in peers.items() if k != cid}
            client = PrintingClient(client_id=cid, port=port, peer_addresses=peer_map, printer_address='localhost:50051')
            client.start_server()
            # guardar para tearDown
            self.clients.append(client)

        # small delay to ensure client servers are up
        time.sleep(0.2)

        # Now connect to peers (after all servers started)
        for client in self.clients:
            client.connect_to_peers()

        # Build map by id
        for client in self.clients:
            clients[client.client_id] = client

        return clients

    def test_scenario_1_basic_no_concurrency(self):
        print("\n\n\nCenário 1: Um cliente A solicita e imprime sem concorrência.\n\n", end='')

        # Criar dois clientes (A=1, B=2) - B não vai concorrer
        client_defs = [(1, 6001), (2, 6002)]
        clients = self._create_clients(client_defs)

        client_a = clients[1]

        # Executa fluxo de requisição/print/liberação
        client_a.request_to_print("Mensagem do Cliente A - Sem concorrência")

        # Pequena pausa para garantir que o envio chegou no servidor de impressão
        time.sleep(0.1)

        # Verifica que a impressora recebeu exatamente uma impressão
        self.assertEqual(len(self.printed_sequence), 1)
        self.assertEqual(self.printed_sequence[0][0], 1)  # primeiro campo é client_id

        # Cliente A deve ter liberado o recurso
        self.assertEqual(client_a.state, MutexState.RELEASED)

    def test_scenario_2_concurrency(self):
        print("\n\n\nCenário 2: Clientes A e B solicitam simultaneamente enquanto C está usando.\n\n", end='')

        # Clientes: A=1, B=2, C=3
        client_defs = [(1, 6011), (2, 6012), (3, 6013)]
        clients = self._create_clients(client_defs)

        client_a = clients[1]
        client_b = clients[2]
        client_c = clients[3]

        # Definir threads para simular comportamento
        def c_work():
            # C entra primeiro e segura a seção crítica
            client_c.request_critical_section()
            # Mantém recurso ocupado para que A e B enviem requisições enquanto C está HELD
            time.sleep(0.4)
            # Faz a impressão enquanto está na seção crítica
            client_c.print_document("Mensagem do Cliente C")
            # Libera recurso
            client_c.release_critical_section()

        def a_work():
            # A solicita um pouco antes de B para ter menor timestamp
            time.sleep(0.05)
            client_a.request_to_print("Mensagem do Cliente A")

        def b_work():
            # B solicita logo em seguida
            time.sleep(0.09)
            client_b.request_to_print("Mensagem do Cliente B")

        # Inicia threads
        t_c = threading.Thread(target=c_work)
        t_a = threading.Thread(target=a_work)
        t_b = threading.Thread(target=b_work)

        t_c.start()
        # Garante que C iniciou antes de A/B
        time.sleep(0.02)
        t_a.start()
        t_b.start()

        # Aguarda término
        t_a.join()
        t_b.join()
        t_c.join()

        # Deve ter 3 impressões: C primeiro, depois A (menor ts) depois B
        self.assertEqual(len(self.printed_sequence), 3)
        # Ordem esperada: C (id 3), A (id 1), B (id 2)
        self.assertEqual(self.printed_sequence[0][0], 3)
        self.assertEqual(self.printed_sequence[1][0], 1)
        self.assertEqual(self.printed_sequence[2][0], 2)


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
