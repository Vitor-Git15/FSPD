"""
Author: Vitor Emanuel Ferreira Vital
Email: vitoremanuelg147@gmail.com
Date: 01/2024
"""

import grpc
import sys

import banco_pb2, banco_pb2_grpc

# definições
MIN_ARGS = 3

SUCCESS = 0
NON_EXISTENT = -1
INVALID_BALANCE = -2
INVALID_WALLET = -3

EXIT_ERROR = -1

INADDR_ANY = '0.0.0.0' # IP que permite conexão com todo IP associado a máquina no qual está executando

# classe no qual as operações de cliente do banco são implementadas
class ClienteBanco:
    def __init__(self, wallet_id, server_address, debug_mode=False):
        """
        Inicializa uma instância do cliente de banco para interagir com um servidor gRPC.

        Args:
            wallet_id (str): O ID da carteira associada ao cliente.
            server_address (str): O endereço do servidor gRPC ao qual o cliente irá se conectar, 
                                  no formato "hostname:port".
            debug_mode (bool, opcional): Se True, ativa o modo de depuração. O padrão é False.

        Atributos:
            wallet_id (str): O ID da carteira associada ao cliente.
            server_address (str): O endereço do servidor gRPC ao qual o cliente está conectado.
            debug_mode (bool): Indica se o modo de depuração está ativado.
            channel (grpc.Channel): O canal de comunicação inseguro para o servidor gRPC.
            stub (banco_pb2_grpc.BancoStub): O stub do cliente para interagir com o serviço Banco.
            order_id (int, opcional): O ID da ordem de pagamento, inicializado como None.
        """
        self.wallet_id = wallet_id
        self.server_address = server_address
        self.debug_mode = debug_mode
        self.channel = grpc.insecure_channel(server_address)
        self.stub = banco_pb2_grpc.BancoStub(self.channel)
        self.order_id = None

    def get_balance(self):
        """
        Solicita e imprime o saldo da carteira associada ao cliente.

        Envia uma solicitação para o servidor gRPC para obter o saldo da carteira identificada pelo `wallet_id` do cliente.

        Caso a solicitação seja bem-sucedida, o saldo é impresso no console. Se ocorrer um erro durante a comunicação com o servidor gRPC, 
        o erro é capturado e uma mensagem de erro é impressa no console se o modo de depuração estiver ativado.
        """
        request = banco_pb2.BalanceRequest(wallet_id=self.wallet_id)
        try:
            response = self.stub.get_balance(request)
            print(response.balance)
        except grpc.RpcError as e:
            self.debug_print(f"Error getting balance: {e}")
    
    def create_payment_order(self, amount):
        """
        Cria uma ordem de pagamento para a carteira associada ao cliente.

        Envia uma solicitação para o servidor gRPC para criar uma ordem de pagamento com um valor especificado (`amount`) para a carteira 
        identificada pelo `wallet_id` do cliente.

        Caso a solicitação seja bem-sucedida, o status da ordem de pagamento é impresso no console. Se ocorrer um erro durante a comunicação 
        com o servidor gRPC, o erro é capturado e uma mensagem de erro é impressa no console se o modo de depuração estiver ativado.

        Args:
            amount (int): O valor da ordem de pagamento a ser criada. Deve ser um inteiro positivo.
        """
        request = banco_pb2.PaymentOrderRequest(wallet_id=self.wallet_id, amount=amount)
        try:
            response = self.stub.create_payment_order(request)
            print(response.status)
        except grpc.RpcError as e:
            self.debug_print(f"Error creating payment order: {e}")
            
    def transfer(self, order_id, confirmation_value, target_wallet_id):
        """
        Processa uma transferência de pagamento para uma carteira de destino.

        Envia uma solicitação para o servidor gRPC para processar uma transferência com base no ID da ordem de pagamento (`order_id`), o valor a
        ser tranferido (`confirmation_value`) e um ID de carteira de destino (`target_wallet_id`).

        Se a transferência for bem-sucedida, o status da transferência é impresso no console. Se ocorrer um erro durante a comunicação com o servidor gRPC,
        o erro é capturado e uma mensagem de erro é impressa no console se o modo de depuração estiver ativado.

        Args:
            order_id (int): O ID da ordem de pagamento que deve ser transferida.
            confirmation_value (int): O valor a ser confirmado e transferido.
            target_wallet_id (str): O ID da carteira de destino para onde o valor deve ser transferido.
        """
        request = banco_pb2.TransferRequest(
            order_id=order_id,
            confirmation_amount=confirmation_value,
            wallet_id=target_wallet_id
        )
        try:
            response = self.stub.transfer(request)
            print(response.status)
        except grpc.RpcError as e:
            self.debug_print(f"Error processing transfer: {e}")
    
    def end_execution(self):
        """
        Envia uma solicitação para encerrar a execução e exibe o número de ordens pendentes.

        Envia uma solicitação ao servidor gRPC para encerrar a execução. Após o servidor processar a solicitação, o número de ordens pendentes 
        é impresso no console. Se ocorrer um erro durante a comunicação com o servidor gRPC, o erro é capturado e uma mensagem de erro é 
        impressa no console se o modo de depuração estiver ativado.

        Após a comunicação com o servidor, o canal gRPC é fechado e o programa é encerrado.
        """
        request = banco_pb2.EndExecutionRequest()
        try:
            response = self.stub.end_execution(request)
            print(response.pending_orders)
        except grpc.RpcError as e:
            self.debug_print(f"Error ending execution: {e}")
            print(EXIT_ERROR)
        finally:
            self.channel.close()
            sys.exit()
    
    def debug_print(self, message):
        """
        Imprime a mensagem recebida se o modo debug estiver ativo.
        Args:
            message: A mensagem a ser impressa
        """
        if self.debug_mode:
            print(f"DEBUG: {message}")
            
    def process_commands(self, input_stream):
        """
        Processa comandos lidos a partir de um fluxo de entrada.

        Este método lê comandos linha por linha a partir do `input_stream`. Cada linha deve conter um comando seguido por argumentos específicos. 
        Os comandos reconhecidos são:

        - 'S': Obtém e imprime o saldo da carteira associada ao cliente.
        - 'O': Cria uma ordem de pagamento com o valor especificado. Requer um argumento adicional, o valor inteiro.
        - 'X': Processa uma transferência com base em um ID de ordem, um valor a ser transferido e um ID de carteira de destino. Requer três argumentos adicionais.
        - 'F': Encerra a execução, imprime o número de ordens pendentes e finaliza o programa.

        Se um comando não for reconhecido ou se os argumentos fornecidos não estiverem no formato correto, o erro é registrado se o modo de depuração estiver ativado.

        Args:
            input_stream (iterable): Um iterador ou fluxo de entrada de linhas de comando. Cada linha deve estar no formato esperado para um dos comandos reconhecidos.
        """
        for line in input_stream:
            line = line.strip()
            if not line:
                continue
            
            commands = line.split()
            command = commands[0]
            
            if command == 'S':
                self.get_balance()
            elif command == 'O':
                if len(commands) != 2:
                    self.debug_print("Invalid 'O' command format.")
                    continue
                value = int(commands[1])
                self.create_payment_order(value)
            elif command == 'X':
                if len(commands) != 4:
                    self.debug_print("Invalid 'X' command format.")
                    continue
                order_id = int(commands[1])
                confirmation_value = int(commands[2])
                target_wallet_id = commands[3]
                self.transfer(order_id, confirmation_value, target_wallet_id)
            elif command == 'F':
                self.end_execution()
            else:
                self.debug_print(f"Ignored unknown command: {line}")
            
def use():
    print(f"Usage: python3 {sys.argv[0]} <wallet_id> <server_address>")


def parse_args(args: list[str]):
    """
    Analisa a lista de argumentos da linha de comando para extrair parâmetros necessários.

    Este método analisa os argumentos fornecidos para determinar o ID da carteira, o endereço do servidor e o modo de depuração. 
    O formato esperado dos argumentos é o seguinte:
    - `args[0]`: O nome do script (não utilizado no método).
    - `args[1]`: O ID da carteira.
    - `args[2]`: O endereço do servidor.
    - `args[3]` (opcional): Se fornecido e igual a 'debug', ativa o modo de depuração.

    Se a quantidade de argumentos for menor que o mínimo necessário (`MIN_ARGS`), o método exibe uma mensagem de uso e encerra o programa com um código de erro.

    Args:
        args (list[str]): Lista de argumentos da linha de comando.

    Returns:
        tuple: Uma tupla contendo três elementos:
            - `wallet_id` (str): O ID da carteira.
            - `server_address` (str): O endereço do servidor.
            - `debug_mode` (bool): `True` se o modo de depuração estiver ativado, `False` caso contrário.
    """
    
    if len(args) < MIN_ARGS:
        use(); exit(1)
        
    wallet_id = sys.argv[1]
    server_address = sys.argv[2]
    debug_mode = len(sys.argv) == 4 and sys.argv[3] == 'debug'
    
    return wallet_id, server_address, debug_mode


def main():
    wallet_id, server_address, debug_mode = parse_args(sys.argv)
    cliente = ClienteBanco(wallet_id, server_address, debug_mode)
    cliente.process_commands(sys.stdin)

if __name__ == "__main__":
    main()