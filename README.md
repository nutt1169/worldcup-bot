# WorldCup Bot

Line Bot ทายผลบอลโลก

## Setup

```bash
cd worldcup-bot
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# แก้ค่าใน .env
uvicorn app.main:app --reload
```

## Deploy (Railway)
1. push ขึ้น GitHub
2. สร้าง project ใน railway.app
3. เพิ่ม environment variables จาก .env.example
4. Railway จะ deploy อัตโนมัติ
