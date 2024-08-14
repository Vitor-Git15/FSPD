
# Author: Vitor Emanuel Ferreira Vital \
  Email: vitoremanuelg147@gmail.com \
  Date: 01/2024


# Diretório principal
MAIN_DIR = .

# Arquivos Proto
BANCO_PROTO = $(MAIN_DIR)/banco.proto
LOJA_PROTO = $(MAIN_DIR)/loja.proto

# Arquivos python
BANCO_CLIENT = $(MAIN_DIR)/cln_banco.py
BANCO_SERVER = $(MAIN_DIR)/svc_banco.py
LOJA_CLIENT = $(MAIN_DIR)/cln_loja.py
LOJA_SERVER = $(MAIN_DIR)/svc_loja.py

# Arquivos Stub
BANCO_STUBS = banco_pb2.py banco_pb2_grpc.py
LOJA_STUBS = loja_pb2.py loja_pb2_grpc.py

.PHONY: clean stubs run_serv_banco run_cli_banco run_serv_loja run_cli_loja copy

# Método que remove os strubs
clean:
	rm -f $(BANCO_STUBS) $(LOJA_STUBS)

# Método que gera os stubs
stubs: $(BANCO_STUBS) $(LOJA_STUBS)

$(BANCO_STUBS): $(BANCO_PROTO)
	python3 -m grpc_tools.protoc -I$(MAIN_DIR) --python_out=. --grpc_python_out=. $(BANCO_PROTO)

$(LOJA_STUBS): $(LOJA_PROTO)
	python3 -m grpc_tools.protoc -I$(MAIN_DIR) --python_out=. --grpc_python_out=. $(LOJA_PROTO)

# Roda o servidor do banco
run_serv_banco: stubs
	python3 $(BANCO_SERVER) $(arg1)

# Roda o cliente do banco
run_cli_banco: stubs
	python3 $(BANCO_CLIENT) $(arg1) $(arg2) $(arg3)

# Roda o servidor da loja
run_serv_loja: stubs
	python3 $(LOJA_SERVER) $(arg1) $(arg2) $(arg3) $(arg4)

# Roda o cliente da loja
run_cli_loja: stubs
	python3 $(LOJA_CLIENT) $(arg1) $(arg2) $(arg3) $(arg4) 
