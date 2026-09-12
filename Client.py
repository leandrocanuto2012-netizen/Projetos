import requests
import time

URL = "https://oozy-unsnap-cement.ngrok-free.dev" # Substitua pela sua URL do Ngrok

while True:
	try:
		response = requests.get(URL)
		if response.status_code == 200:
			print("Conexão ativa.")
		else:
			print(f"Erro na conexão: Status {response.status_code}")
	except requests.exceptions.RequestException as e:
		print(f"Falha na conexão: {e}. Tentando reconectar...")

	time.sleep(60) # Intervalo entre as checagens em segundos