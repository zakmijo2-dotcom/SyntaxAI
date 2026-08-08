# SyntaxAI - Terminal AI Programming Assistant

SyntaxAI هو وكيل برمجي ذكي يعمل من الطرفية، يحوّل التيرمنال إلى مبرمج مساعد قادر على قراءة المشاريع، تعديلها، تنفيذ أوامر، والتكامل مع GitHub.

## المتطلبات

- Python 3.10+
- حزمة من حزم الاعتمادية الأساسية (pyyaml, httpx)
- مفتاح API من أحد المزودين: Google Gemini، DeepSeek، أو Nemotron

## التثبيت على Termux

```bash
# استنساخ المشروع
git clone https://github.com/SyntaxAI/syntaxai.git
cd syntaxai

# تشغيل سكربت التثبيت
bash install.sh
```

## التثبيت على GitHub Codespaces

```bash
# في محطة الأوامر داخل Codespace
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## إعداد مفاتيح API

### Google Gemini
```bash
export gemini_api_key="YOUR_API_KEY"
```

### DeepSeek
```bash
export deepseek_api_key="YOUR_API_KEY"
```

### Nemotron
```bash
export nemotron_api_key="YOUR_API_KEY"
```

## الاستخدام الأساسي

```bash
# بدء الـ REPL
syntaxai

# أو مع مزود محدد
syntaxai --provider gemini --model gemini-1.5-flash

# أو باستخدام سكربت Python مباشرة
python main.py
```

### الأوامر المتوفرة في الـ REPL

| الأمر | الوصف |
|-------|-------|
| `read_file(path)` | قراءة محتوى الملف |
| `write_file(path, content)` | كتابة محتوى جديد للملف |
| `edit_file(path, old, new)` | تعديل الملف باستخدام diff |
| `list_tree(path, depth)` | عرض شجرة المجلدات |
| `shell(command)` | تنفيذ أمر Shell |
| `git_status` | عرض حالة المستودع |
| `git_diff` | عرض الفرق |
| `git_commit(message)` | عمل commit |
| `git_push(remote, branch)` | دفع التغييرات |

## نظام الموافقة والسلامة

يتطلب SyntaxAI الموافقة الصريحة قبل:

- **أوامر آمنة**: ينفذ مباشرة (ls, cat, git status)
- **أوامر متوسطة الخطورة**: يطلب تأكيد (تثبيت حزم، git commit)
- **أوامر عالية الخطورة**: يطلب تأكيداً مضاعفاً مع شرح (rm -rf, git push --force)

## إضافة Skill جديدة

1. أنشئ مجلدًا في `.skills/` باسم المهارة:
```bash
mkdir .skills/my-skill
```

2. أنشئ ملف `SKILL.md` داخل المجلد:
```markdown
---
name: My Custom Skill
description: Skills that helps with specific task
triggers:
  - "my task"
  - "custom operation"
enabled: true
---

Your skill content here...
```

## الهيكل التلقائي للمشروع

```
syntaxai/
├── main.py                    # نقطة الدخول
├── syntaxai/
│   ├── core/                  # المنطق الأساسي
│   ├── providers/             # مزودي LLM
│   ├── tools/                 # الأدوات المتاحة
│   ├── safety/                # نظام الأمان
│   └── ui/                    # واجهة المستخدم
├── requirements.txt
├── pyproject.toml
├── README.md
└── install.sh
```

## الملفات الحساسة التي يتم حمايتها

SyntaxAI يمنع الوصول إلى الملفات التالية تلقائيًا:
- ملفات `.env`
- ملفات `*.key`, `*.pem`, `*.crt`
- مجلدات `.git/`
- ملفات الاعتمادية

## سجل الأوامر

جميع الأوامر المنفذة تُحفظ في `~/.syntaxai/logs/` مع الوقت والنتيجة.