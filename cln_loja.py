"""
Author: Vitor Emanuel Ferreira Vital
Email: vitoremanuelg147@gmail.com
Date: 01/2024
"""

import grpc
import sys

import banco_pb2, banco_pb2_grpc
import loja_pb2, loja_pb2_grpc

# definições
MIN_ARGS = 3

SUCCESS = 0
NON_EXISTENT = -1
INVALID_BALANCE = -2
INVALID_WALLET = -3

EXIT_ERROR = -1

INADDR_ANY = '0.0.0.0' # IP que permite conexão com todo IP associado a máquina no qual está executando

# classe no qual as operações de cliente da loja são implementadas
class ClienteLoja:
    def __init__(self, wallet_id, bank_address, store_address, debug_mode=False):
        """
        Inicializa um cliente da loja, configurando canais e stubs para comunicação com o banco e a loja.

        Este construtor cria canais de comunicação gRPC para se conectar ao servidor bancário e ao servidor da loja. Ele também obtém o preço do produto disponível na loja.

        Args:
            wallet_id (str): O ID da carteira do cliente.
            bank_address (str): O endereço do servidor bancário.
            store_address (str): O endereço do servidor da loja.
            debug_mode (bool, opcional): Se True, habilita o modo de depuração para exibir mensagens adicionais. O padrão é False.
            
        Attributes:
            wallet_id (str): ID da carteira do cliente.
            bank_address (str): Endereço do servidor bancário.
            store_address (str): Endereço do servidor de loja.
            debug_mode (bool): Indica se o modo de depuração está ativado.
            bank_channel (grpc.Channel): Canal de comunicação com o servidor bancário.
            bank_stub (banco_pb2_grpc.BancoStub): Stub para chamadas ao servidor bancário.
            store_channel (grpc.Channel): Canal de comunicação com o servidor de loja.
            store_stub (loja_pb2_grpc.LojaStub): Stub para chamadas ao servidor de loja.
            product_price (int): Preço do produto obtido do servidor de loja (inicialmente None).
        """
        self.wallet_id = wallet_id
        self.bank_address = bank_address
        self.store_address = store_address
        self.debug_mode = debug_mode
        
        self.bank_channel = grpc.insecure_channel(bank_address)
        self.bank_stub = banco_pb2_grpc.BancoStub(self.bank_channel)
        
        self.store_channel = grpc.insecure_channel(store_address)
        self.store_stub = loja_pb2_grpc.LojaStub(self.store_channel)
        
        self.product_price = None
        self.get_product_price()

    def get_product_price(self):
        """
        Consulta o preço do produto no servidor de loja e armazena o valor obtido.

        Este método envia uma solicitação ao servidor de loja para obter o preço atual do produto. O preço é então armazenado no atributo `product_price` e impresso no console.

        Se ocorrer um erro durante a solicitação gRPC, uma mensagem de erro é exibida no console, utilizando o método `debug_print` se o modo de depuração estiver ativado.
        """
        request = loja_pb2.PriceRequest()
        try:
            response = self.store_stub.get_price(request)
            self.product_price = response.price
            print(self.product_price)
        except grpc.RpcError as e:
            self.debug_print(f"Error getting product price: {e}")
    
    def purchase_product(self):
        """
        Processa a compra de um produto realizando um pedido de pagamento e, se bem-sucedido, efetuando a compra no servidor de loja.

        O método verifica se o preço do produto está definido. Se não estiver, exibe uma mensagem de erro e retorna imediatamente. 
        Caso o preço esteja definido, o método cria um pedido de pagamento no servidor bancário com o valor do produto. Se o pedido de pagamento for bem-sucedido, 
        o método usa o ID da ordem para solicitar a compra do produto ao servidor de loja.

        Se ocorrer algum erro durante o processo de compra, uma mensagem de erro é exibida no console, utilizando o método `debug_print` se o modo de depuração estiver ativado. 
        Se o status do pedido de pagamento for inválido, o método retorna um erro de saída.
        """
        if self.product_price is None:
            self.debug_print("Product price is not set.")
            return
    
        order_request = banco_pb2.PaymentOrderRequest(wallet_id=self.wallet_id, amount=self.product_price)
        try:
            order_response = self.bank_stub.create_payment_order(order_request)
            status = order_response.status
            print(status)
            if status <= 0:
                return  EXIT_ERROR

            sale_request = loja_pb2.SaleRequest(order_id=status)
            sale_response = self.store_stub.sale(sale_request)
            
            print(sale_response.status)
        
        except grpc.RpcError as e:
            self.debug_print(f"Error during purchase: {e}")
    
    def end_execution(self):
        """
        Finaliza a execução do cliente fechando as conexões com os servidores e exibindo o saldo do vendedor e o status do servidor bancário.

        O método envia uma solicitação para o servidor de loja para encerrar a execução. Em seguida, imprime o saldo do vendedor e o status do servidor bancário retornados na resposta. 
        Se ocorrer um erro durante o processo, uma mensagem de erro é exibida no console e valores de erro (-1) são impressos. Após isso, o método fecha as conexões com os servidores 
        bancário e de loja e encerra o programa com um código de saída 0.
        """
        request = loja_pb2.EndExecutionRequest()
        try:
            response = self.store_stub.end_execution(request)
            print(response.seller_balance, response.bank_server_status)
        except grpc.RpcError as e:
            self.debug_print(f"Error ending store server: {e}")
            print(-1, -1)
        finally:
            self.bank_channel.close()
            self.store_channel.close()
            sys.exit(0)
    
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
        Processa comandos lidos de um fluxo de entrada e executa ações baseadas nesses comandos.

        O método lê linhas do fluxo de entrada, analisa cada linha para identificar o comando e, com base no comando, executa a ação correspondente. Os comandos suportados são:
        - 'C': Chama o método `purchase_product()` para realizar uma compra de produto.
        - 'T': Chama o método `end_execution()` para finalizar a execução e encerrar o programa.

        Se um comando desconhecido for encontrado, uma mensagem de depuração é impressa.

        Args:
            input_stream (iterable): Um fluxo de entrada que fornece linhas de comandos a serem processados.
        """
        for line in input_stream:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split()
            command = parts[0]
            
            if command == 'C':
                self.purchase_product()
            elif command == 'T':
                self.end_execution()
            else:
                self.debug_print(f"Ignored unknown command: {line}")
            
def use():
    print(f"Usage: python3 {sys.argv[0]} <wallet_id> <server_address>")


def parse_args(args: list[str]):
    """
    Analisa argumentos da linha de comando para configurar parâmetros do cliente.

    O método verifica a quantidade de argumentos fornecidos e valida se estão corretos. A seguir, extrai os parâmetros necessários para configurar o cliente, incluindo o ID da carteira, 
    o endereço do banco, o endereço da loja e o modo de depuração. 

    Args:
        args (list[str]): Uma lista de argumentos da linha de comando. Espera-se que contenha pelo menos três argumentos além do nome do script, com o formato:
            - args[1]: ID da carteira (wallet_id)
            - args[2]: Endereço do banco (bank_address)
            - args[3]: Endereço da loja (store_address)
            - args[4]: (Opcional) 'debug' para ativar o modo de depuração

    Returns:
        tuple: Uma tupla contendo os seguintes valores:
            - wallet_id (str): O ID da carteira.
            - bank_address (str): O endereço do banco.
            - store_address (str): O endereço da loja.
            - debug_mode (bool): Verdadeiro se o modo de depuração estiver ativado, caso contrário, Falso.
    """
    if len(args) < MIN_ARGS:
        use(); exit(1)
        
    wallet_id = sys.argv[1]
    bank_address = sys.argv[2]
    store_address = sys.argv[3]
    debug_mode = len(sys.argv) == 4 and sys.argv[3] == 'debug'
    
    return wallet_id, bank_address, store_address, debug_mode


def main():
    wallet_id, bank_address, store_address, debug_mode = parse_args(sys.argv)
    cliente = ClienteLoja(wallet_id, bank_address, store_address, debug_mode)
    
    cliente.process_commands(sys.stdin)

if __name__ == "__main__":
    main()