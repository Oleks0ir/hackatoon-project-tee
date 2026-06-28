# DayTEE 🍵🔒

> **Confidential AI Matchmaking in Secure Hardware Enclaves**
> 
> *A project by Team **Kolosok** (TUM Science Hackathon 2026)*

## ❤️🔐 The Concept

**DayTEE is a privacy-first matchmaking application (dating app) on secure enclaves**

DayTEE uses private AI analysis inside secure hardware vaults (TEEs) to find highly compatible partners. By performing remote attestation, we guarantee your profile, messages, and chat metadata remain completely hidden from everyone, including the developers. Profiles and chats are invisible until our algorithm verifies a strong match. No public directories, no endless swiping, and absolute privacy.

You can test the app here:
https://34.6.215.42.sslip.io/

---

## 💡 Naming
**DayTEE** is a privacy-first matchmaking application built on secure enclaves. The name is a multi-layered pun:
1. **Dating / "Date-y" (`DayTEE`)**: Emphasizes our core goal—bringing people together for romantic connections and day dates.
2. **Tea Time (`Tea`)**: Represents cozy, casual first-date encounters over a cup of tea. It also references "spilling the tea" (sharing your life stories in complete confidence).
3. **Trusted Execution Environment (`TEE`)**: Emphasizes our core security architecture. Your profile data and life stories are never visible in plaintext on server hard disks; they are encrypted and processed inside secure CPU hardware enclaves (Intel TDX / AMD SEV).

---

## 🚀 Setup & Execution

### Prerequisites
- **Python 3.9+** (installed on local system)
- **Node.js & npm**

---



### Step 1: Start the Matchmaking Backend
1. Navigate to the `server/` directory:
   ```bash
   cd server
   ```
2. Install the python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the uvicorn API server on port `8765`:
   ```bash
   python -m uvicorn app:app --port 8765
   ```
   *The database is mocked in `server/db.json` and cleared automatically upon reset.*

---

### Step 2: Start the Client Web App
1. Navigate to the `client/` directory:
   ```bash
   cd ../client
   ```
2. Install standard Node server dependencies (if first time running):
   ```bash
   npm install
   ```
3. Run the static file dev server:
   ```bash
   node server.js
   ```
   *The app is served at [http://localhost:3000](http://localhost:3000).*

---

## 🔒 Security Principles
- **Zero public directory**: No directories, matching lists, or swipe lists exist. Users only discover each other when a highly compatible cryptographic matching channel is generated inside the enclave.
- **Ephemeral Storage**: Server data is stored inside local RAM enclaves. Admin triggers or server power cycles wipe all memory logs automatically.

-----------

After ssh:
```
cd ~/hackatoon-project-tee
git pull origin main
sudo systemctl restart tee-backend tee-frontend
```
