# 🔍 EmailFinder - OSINT Email Discovery Tool

Un outil OSINT avancé pour rechercher des adresses email associées à une personne via son prénom/nom.

## ⚡ Fonctionnalités

- **🔥 Multi-sources** : Hunter.io, HIBP, LeakCheck, Archives web, GitHub
- **🎯 3 modes** : Quick (2min), Medium (10min), Complete (20min)
- **📊 Scoring intelligent** : Emails classés par fiabilité
- **🛡️ Respectueux** : Rate limiting, robots.txt

## 🚀 Installation

```bash
git clone https://github.com/PxpSy/EmailFinder.git
cd EmailFinder
pip install -r requirements.txt
```

## ⚙️ Configuration

### **1. Configuration des APIs**
Créer un fichier `.env`:
```bash
HUNTER_API_KEY=votre_cle_api_hunter_io
```

Obtenir une clé API Hunter.io (gratuite) : [hunter.io](https://hunter.io)

### **2. Configuration des profils à rechercher**

Modifier dans le fichier `emailfinder.py` (ligne 1890) :

```python
profils = [
    # Recherche basique (nom/prénom uniquement)
    {"prenom": "Alan", "nom": "Turing", "domaine": ""},
    
    # Recherche ciblée sur un domaine spécifique
    {"prenom": "Jean", "nom": "Dupont", "domaine": "entreprise.com"},
    
    # Recherche multiple
    {"prenom": "Marie", "nom": "Martin", "domaine": "universite.fr"},
    {"prenom": "Pierre", "nom": "Bernard", "domaine": ""},
]
```

### **3. Types de configuration**

#### **🎯 Recherche générale (recommandée)**
```python
{"prenom": "Alan", "nom": "Turing", "domaine": ""}
```
- ✅ Recherche dans **tous les domaines publics**
- ✅ Utilise **15+ sources différentes**
- ✅ **Plus de résultats** potentiels

#### **🏢 Recherche ciblée entreprise**
```python
{"prenom": "Jean", "nom": "Dupont", "domaine": "microsoft.com"}
```
- ✅ **Plus précis** pour emails professionnels
- ✅ **Hunter.io optimisé** pour ce domaine
- ✅ Moins de faux positifs

#### **🎓 Recherche académique**
```python
{"prenom": "Marie", "nom": "Curie", "domaine": "sorbonne-universite.fr"}
```
- ✅ Focus sur **emails universitaires**
- ✅ Recherche dans **publications scientifiques**

## 💻 Utilisation

```bash
# Test rapide (2min)
python emailfinder.py quick

# Recherche moyenne (15min) 
python emailfinder.py medium

# Recherche complète (60min)
python emailfinder.py complete

# Tests de configuration
python emailfinder.py debug
```

## 🔍 **Comment ça fonctionne ?**

### **Impact du domaine sur la recherche :**

#### **Sans domaine spécifique (`domaine: ""`)** 🌐
```python
{"prenom": "Alan", "nom": "Turing", "domaine": ""}
```

**✅ Avantages :**
- Recherche **exhaustive** sur 15+ sources
- Emails **personnels et professionnels**
- **Maximum de résultats** potentiels

**⚠️ Inconvénients :**
- Plus de **faux positifs** possibles
- Temps de recherche **plus long**

#### **Avec domaine spécifique** 🏢
```python
{"prenom": "Alan", "nom": "Turing", "domaine": "cambridge.edu"}
```

**✅ Avantages :**
- **Précision maximale** pour ce domaine
- **Hunter.io optimisé** (Email Finder + Domain Search)
- **Résultats plus fiables**

**⚠️ Inconvénients :**
- **Emails externes manqués** (Gmail, Outlook, etc.)
- Résultats **limités à ce domaine**

### **Processus de recherche détaillé :**

#### **1. Génération de requêtes intelligentes** 🎯
L'outil génère automatiquement **100+ requêtes Google spécialisées** :

```
🔍 Requêtes par plateforme :
  • site:linkedin.com "alan turing"
  • site:github.com "alan" "turing" 
  • site:twitter.com "alan turing"
  • site:academia.edu "alan turing"
  • site:researchgate.net "alan" "turing"

🔍 Requêtes par type de données :
  • "alan turing" filetype:pdf
  • "alan turing" "@"
  • "alan turing" intext:"email"
  • site:pastebin.com "alan turing" "@"

🔍 Requêtes avec domaine ciblé :
  • site:cambridge.edu "alan turing"
  • "alan turing" "@cambridge.edu"
  • filetype:pdf "alan turing" site:cambridge.edu
```

#### **2. Extraction de liens** 🌐
Pour chaque requête, l'outil extrait les liens pertinents :

```
🔗 Exemple de résultats typiques :
  • 3-40 liens par requête Google
  • Total: 500+ liens uniques explorés
  • Filtrage automatique des doublons
  
🎯 Types de liens trouvés :
  • Profils sociaux (LinkedIn, Twitter, GitHub)
  • Articles de presse mentionnant la personne  
  • Documents PDF avec coordonnées
  • Archives web et bases publiques
  • Sites académiques et professionnels
```

#### **3. Scraping intelligent** 🤖
Chaque lien est analysé pour extraire des emails :

```
📧 Techniques d'extraction :
  • Regex avancée pour emails valides
  • Analyse de documents PDF/DOC
  • Parsing HTML et métadonnées
  • Extraction depuis JavaScript (Selenium)
  
⚡ Traitement parallèle :
  • 10 liens analysés simultanément
  • Timeout de 15s par page
  • Gestion d'erreurs robuste
```

#### **4. Validation et scoring** 📊
Les emails trouvés sont validés et scorés :

```
🏆 Système de scoring (0-50 points) :
  • Hunter.io vérifié : 35 points
  • Source officielle : 25-30 points  
  • Mention sur site personnel : 20 points
  • Archives/PDF : 15 points
  • Génération probable : 3-5 points

✅ Validations appliquées :
  • Format email correct (RFC 5322)
  • Domaine DNS valide
  • Filtrage anti-spam basique
  • Dédoublonnage intelligent
```

## 📊 **Exemples de résultats**

### **Exemple 1: Recherche générale**
```python
{"prenom": "Alan", "nom": "Turing", "domaine": ""}
```

```
🎯 Recherche pour: alan turing
⏱️ Temps d'exécution: 19.5 minutes
🔗 Links analysés: 514 sites web

📊 ANALYSE DÉTAILLÉE:
  📧 Total emails trouvés: 12
  🔗 Total liens explorés: 514
  📊 Sources utilisées:
    - hunter_verified_probable: 3 emails ⭐
    - cambridge.edu: 2 emails (université)
    - github.com: 2 emails (profil dev)
    - sites d'actualités: 3 emails (mentions presse)
    - generated_probable: 2 emails

🏆 Top 3 emails par fiabilité:
  1. alan.turing@cambridge.edu (score: 35) - Hunter.io vérifié
  2. a.turing@manchester.ac.uk (score: 30) - Source officielle  
  3. aturing@github.com (score: 25) - Profil GitHub
```

### **Exemple 2: Recherche ciblée**
```python
{"prenom": "Alan", "nom": "Turing", "domaine": "cambridge.edu"}
```

```
🎯 Recherche pour: alan turing @ cambridge.edu
⏱️ Temps d'exécution: 8.2 minutes
🔗 Links analysés: 156 sites web

📊 ANALYSE DÉTAILLÉE:
  📧 Total emails trouvés: 5
  🔗 Total liens explorés: 156
  📊 Sources utilisées:
    - hunter.io_finder: 2 emails ⭐⭐⭐
    - hunter.io_domain: 2 emails ⭐⭐
    - cambridge.edu: 1 email

🏆 Top 3 emails par fiabilité:
  1. alan.turing@cambridge.edu (score: 45) - Hunter Email Finder
  2. a.m.turing@cambridge.edu (score: 42) - Hunter Domain Search
  3. turing@cam.ac.uk (score: 35) - Site officiel
```

## 💡 **Conseils d'utilisation**

### **🎯 Quand utiliser quel type de recherche ?**

#### **Recherche GÉNÉRALE** (`domaine: ""`)
**✅ Recommandée pour :**
- Personnes **inconnues** ou **freelance**
- Recherche **OSINT complète**
- **Première recherche** exploratoire
- Personnes avec **activité web diverse**

#### **Recherche CIBLÉE** (`domaine: "entreprise.com"`)
**✅ Recommandée pour :**
- **Employees connus** d'une entreprise
- **Prospection B2B** ciblée
- **Vérification d'un domaine** spécifique
- **Recherche académique** (universités)

### **📝 Exemples pratiques**

#### **Cas 1: Recruteur cherchant un candidat**
```python
# Candidat travaillant chez Google
{"prenom": "John", "nom": "Smith", "domaine": "google.com"}
```

#### **Cas 2: Journaliste recherchant un expert**
```python
# Expert inconnu, recherche large
{"prenom": "Marie", "nom": "Expert", "domaine": ""}
```

#### **Cas 3: Commercial prospectant une entreprise**
```python
# DRH d'une entreprise cible
{"prenom": "Pierre", "nom": "Martin", "domaine": "target-company.fr"}
```

#### **Cas 4: Recherche multiple pour une campagne**
```python
profils = [
    {"prenom": "CEO", "nom": "Startup", "domaine": "startup.io"},
    {"prenom": "CTO", "nom": "Startup", "domaine": "startup.io"},
    {"prenom": "CMO", "nom": "Startup", "domaine": "startup.io"},
]
```

## 🚨 **Limitations importantes**

### **Cas difficiles** ⚠️
```
❌ Pseudonymes non liés au nom :
  • Nom: "Alan Turing" 
  • Email réel: "crypto_master@protonmail.com"
  • Résultat: Non trouvé (pas de lien apparent)

❌ Aliases créatifs :
  • Nom: "Jean Dupont"
  • Email réel: "snoop.lebraque@hotmail.com" 
  • Résultat: Très difficile à découvrir
```

### **Solutions pour les pseudonymes** 💡
```
✅ Recherche manuelle complémentaire :
  • Rechercher "crypto_master" + nom de famille
  • Vérifier profils GitHub/réseaux sociaux
  • Croiser avec informations connues

✅ Techniques avancées :
  • OSINT sur les pseudonymes connus
  • Analyse des métadonnées de documents
  • Corrélation avec bases de données publiques
```

## ⚖️ Usage légal

Cet outil est destiné à un **usage légitime uniquement** :
- ✅ Recrutement, prospection B2B
- ✅ Journalisme, recherche académique  
- ✅ Tests de sécurité autorisés
- ❌ Spam, harcèlement, usurpation

## 🔒 Respect de la vie privée

- Utilise uniquement des **données publiques**
- Respecte le **RGPD** et robots.txt
- N'accède à **aucune base privée**

## 📝 License

MIT License - Voir [LICENSE](LICENSE)

---

## 🛠️ **Dépannage**

### **Problèmes courants** 🔧

```bash
# Google bloque les requêtes (trop de 403)
⚠️ Solution: Utiliser mode "quick" ou ajouter des proxies

# Aucun email trouvé
⚠️ Solution: Vérifier la clé API Hunter.io et essayer des variantes du nom

# Timeout/erreurs réseau
⚠️ Solution: Réduire le parallélisme ou améliorer la connexion

# Profil mal configuré
⚠️ Solution: Vérifier la syntaxe des profils dans emailfinder.py
```

### **Optimisations** ⚡

```bash
# Recherche plus rapide (15 min)
python emailfinder.py medium

# Focus sur APIs uniquement (2 min)
python emailfinder.py quick

# Debug de configuration
python emailfinder.py debug
```

### **Configuration avancée**

```python
# Recherche multiple avec différents domaines
profils = [
    # Même personne, différents domaines
    {"prenom": "Jean", "nom": "Dupont", "domaine": "ancien-job.com"},
    {"prenom": "Jean", "nom": "Dupont", "domaine": "nouveau-job.fr"},
    {"prenom": "Jean", "nom": "Dupont", "domaine": ""},  # Recherche générale
]
```