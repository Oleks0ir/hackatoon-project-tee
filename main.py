import hashlib
import requests
import os
from fastapi import FastAPI, HTTPException
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

app = FastAPI(title="KOLOSOK TEE Backend")

# Пути к файлам ваших общих ключей
PRIVATE_KEY_PATH = "private_key.pem"
PUBLIC_KEY_PATH = "public_key.pem"

# Глобальные переменные
private_key = None
public_key_pem = None
public_key_hash = None

def load_or_generate_keys():
    """Загружает существующий статический ключ проекта или создает его один раз."""
    global private_key, public_key_pem, public_key_hash
    
    # 1. Проверяем, лежат ли уже ключи в папке проекта
    if os.path.exists(PRIVATE_KEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        with open(PRIVATE_KEY_PATH, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )
        with open(PUBLIC_KEY_PATH, "rb") as key_file:
            public_key_pem = key_file.read().decode('utf-8')
        print("[INIT] Общие статические ключи успешно загружены из файлов.")
        
    else:
        # 2. Если файлов нет, генерируем пару и сохраняем насовсем
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()
        
        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        # Сохраняем приватный ключ в файл
        with open(PRIVATE_KEY_PATH, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
            
        # Сохраняем публичный ключ в файл
        with open(PUBLIC_KEY_PATH, "wb") as f:
            f.write(public_key_pem.encode('utf-8'))
            
        print("[INIT] Файлы ключей не найдены. Сгенерированы и сохранены новые статические ключи.")

    # 3. Вычисление SHA-256 хэша от публичного ключа (для привязки к железу TDX)
    public_key_hash = hashlib.sha256(public_key_pem.encode('utf-8')).hexdigest()

# Запускаем загрузку ключей при старте приложения
load_or_generate_keys()

@app.get("/handshake")
def handshake():
    """
    Эндпоинт для клиента. Возвращает статический публичный ключ и аппаратный Quote.
    """
    if not public_key_hash:
        raise HTTPException(status_code=500, detail="Ключи не инициализированы")

    # Заглушка для локальной разработки на Windows
    quote = "mock_quote_for_local_windows_testing"

    # Пытаемся получить Quote от локального демона Dstack (работает внутри TEE)
    try:
        payload = {"report_data": public_key_hash}
        response = requests.post(
            "http://localhost:8090/prpc/Tappd.RawQuote",
            json=payload,
            timeout=2 
        )
        
        if response.status_code == 200:
            quote = response.json().get("quote", "")
        else:
            print(f"[Warning] Ошибка Tappd: {response.text}")
            
    except requests.exceptions.RequestException:
        print("[Warning] Не удалось подключиться к Dstack. Сервер запущен локально?")

    return {
        "public_key": public_key_pem,
        "quote": quote
    }