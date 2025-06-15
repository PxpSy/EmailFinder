import requests, re, time, random, asyncio, aiohttp
from urllib.parse import quote, urljoin, urlparse
from urllib.robotparser import RobotFileParser
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import concurrent.futures
import PyPDF2, textract
from io import BytesIO
import json
import os
import base64

from dotenv import load_dotenv

load_dotenv()


# 1) Regex robustes pour email
EMAIL_REGEX = re.compile(r"""
    (?:                                       # local-part
        [A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+
        (?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*
      |                                       
        "(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]
         |\\[\x01-\x09\x0b\x0c\x0e-\x7f])*"
    )
    @                                         # @ separator
    (?:
        (?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+
        [A-Za-z]{2,}
      |
        \[
          (?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}
          (?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?
          |[A-Za-z0-9-]*[A-ZaZ0-9]:
            (?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]
             |\\[\x01-\x09\x0b\x0c\x0e-\x7f])+
          )
        \]
    )
""", re.VERBOSE | re.IGNORECASE)


DELIVEREDTO_REGEX = re.compile(r"deliveredto:\s*(" + EMAIL_REGEX.pattern + ")", re.IGNORECASE)

USER_AGENT = "PowerScraper/2.0 (+https://votre.site/bot)"
HEADERS = {"User-Agent": USER_AGENT}

# Configuration Hunter.io
HUNTER_API_KEY = os.getenv('HUNTER_API_KEY', '')  


HUNTER_BASE_URL = "https://api.hunter.io/v2"

# Proxies et User-Agents rotatifs
PROXY_POOL = [
    # Ajouter vos proxies ici (optionnel)
    # "http://proxy1:8080",
    # "http://proxy2:8080",
    # "http://proxy3:8080"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0"
]

# Types de fichiers à analyser
DOCUMENT_TYPES = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xlsx', 'txt']

def generate_email_variations(first_name, last_name):
    """Génère des variations d'emails probables"""
    first = first_name.lower()
    last = last_name.lower()
    
    # Domaines les plus courants
    domains = [
        "gmail.com", "outlook.com", "hotmail.com", "yahoo.fr", "orange.fr", 
        "free.fr", "wanadoo.fr", "sfr.fr", "laposte.net", "live.fr",
        "hotmail.fr", "yahoo.com", "icloud.com", "protonmail.com"
    ]
    
    # Patterns d'emails courants
    patterns = [
        f"{first}.{last}",
        f"{first}{last}",
        f"{first}_{last}",
        f"{first}-{last}",
        f"{first[0]}.{last}",
        f"{first}.{last[0]}",
        f"{first}{last[0]}",
        f"{last}.{first}",
        f"{last}{first}",
        f"{first}",
        f"{last}"
    ]
    
    variations = []
    for pattern in patterns:
        for domain in domains:
            variations.append(f"{pattern}@{domain}")
    
    return variations[:50]  # Limiter à 50 pour éviter spam

def search_social_media(first_name, last_name):
    """Recherche sur les réseaux sociaux publics"""
    results = []
    
    # LinkedIn public (sans API)
    try:
        query = f'"{first_name} {last_name}" site:linkedin.com'
        url = f"https://www.google.com/search?q={quote(query)}"
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            # Recherche de patterns LinkedIn
            linkedin_pattern = r'linkedin\.com/in/([^"]+)'
            matches = re.findall(linkedin_pattern, response.text)
            if matches:
                print(f"  🔗 LinkedIn trouvé: {matches[0]}")
                results.append({
                    "platform": "linkedin",
                    "profile": f"linkedin.com/in/{matches[0]}",
                    "score": 10
                })
    except Exception as e:
        print(f"  ❌ Erreur LinkedIn: {e}")
    
    return results

def validate_email_format(email):
    """Vérifie si un email a un format valide"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def email_domain_exists(email):
    """Vérifie si le domaine de l'email existe (DNS)"""
    try:
        import socket
        domain = email.split('@')[1]
        socket.gethostbyname(domain)
        return True
    except:
        return False

def leakcheck_io_search(email):
    """API gratuite LeakCheck.io (500 requêtes/mois)"""
    try:
      
        url = f"https://leakcheck.io/api/public?check={email}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("found", False):
                print(f"  💥 LeakCheck: Email {email} trouvé dans {data.get('sources', 0)} source(s)")
                return {
                    "email": email,
                    "source": "leakcheck_io",
                    "score": 25,
                    "found": True,
                    "sources_count": data.get("sources", 0)
                }
        print(f"  ✅ LeakCheck: {email} non trouvé")
        return None
    except Exception as e:
        print(f"  ❌ Erreur LeakCheck: {e}")
        return None

def haveibeenpwned_check(email):
    """Vérification via Have I Been Pwned API"""
    try:
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
        headers = {
           "User-Agent": "EmailFinder-Script"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            breaches = response.json()
            print(f"  💥 HIBP: {len(breaches)} breach(es) trouvé(s) pour {email}")
            return breaches
        elif response.status_code == 404:
            print(f"  ✅ HIBP: Aucun breach trouvé pour {email}")
            return []
        elif response.status_code == 429:
            print(f"  ⏰ HIBP: Rate limit atteint pour {email}")
            return []
    except Exception as e:
        print(f"  ❌ Erreur HIBP: {e}")
    return []

def phonebook_cz_search(first_name, last_name):
    """Recherche sur Phonebook.cz (gratuit, pas d'API officielle)"""
    try:
        # Scraping simple du site public
        query = f"{first_name} {last_name}"
        url = f"https://phonebook.cz/search?q={quote(query)}"
        
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Extraction simple d'emails du HTML
            emails = set(EMAIL_REGEX.findall(response.text))
            if emails:
                print(f"  📞 Phonebook.cz: {len(emails)} email(s) trouvé(s)")
                return [{"email": email, "source": "phonebook_cz", "score": 15} for email in emails]
        
        print(f"  ✅ Phonebook.cz: Aucun email trouvé")
        return []
    except Exception as e:
        print(f"  ❌ Erreur Phonebook.cz: {e}")
        return []

def hunter_verify_email(email):
    """Vérifie un email via l'API Hunter.io Email Verifier"""
    if not HUNTER_API_KEY:
        return None
    
    try:
        verify_url = f"{HUNTER_BASE_URL}/email-verifier"
        params = {
            "email": email,
            "api_key": HUNTER_API_KEY
        }
        
        response = requests.get(verify_url, params=params, timeout=10)
        print(f"  🔍 Hunter Verify API call: {response.status_code} pour {email}")
        
        if response.status_code == 200:
            data = response.json()
            verification_data = data.get("data", {})
            
            result = {
                "email": email,
                "result": verification_data.get("result", "unknown"),
                "score": verification_data.get("score", 0),
                "regexp": verification_data.get("regexp", False),
                "gibberish": verification_data.get("gibberish", False),
                "disposable": verification_data.get("disposable", False),
                "webmail": verification_data.get("webmail", False),
                "mx_records": verification_data.get("mx_records", False),
                "smtp_server": verification_data.get("smtp_server", False),
                "smtp_check": verification_data.get("smtp_check", False),
                "accept_all": verification_data.get("accept_all", False),
                "block": verification_data.get("block", False)
            }
            
            status_emoji = {
                "deliverable": "✅",
                "undeliverable": "❌", 
                "risky": "⚠️",
                "unknown": "❔"
            }
            
            emoji = status_emoji.get(result["result"], "❔")
            print(f"    {emoji} Hunter Verify: {email} -> {result['result']} (score: {result['score']})")
            
            return result
            
    except Exception as e:
        print(f"  ❌ Erreur Hunter Verify: {e}")
    
    return None

def hunter_io_search(first_name, last_name, domain=None, company=None):
    """Recherche email via l'API Hunter.io - Version complète"""
    if not HUNTER_API_KEY:
        print("  ⚠️ Clé API Hunter.io manquante")
        return []
    
    emails_found = []
    
    try:
        # 1) Email Finder - recherche par nom/prénom/domaine
        if domain:
            finder_url = f"{HUNTER_BASE_URL}/email-finder"
            params = {
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": HUNTER_API_KEY
            }
            
            response = requests.get(finder_url, params=params, timeout=10)
            print(f"  📡 Email Finder API call: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if data.get("data", {}).get("email"):
                    email_data = data["data"]
                    emails_found.append({
                        "email": email_data["email"],
                        "score": email_data.get("score", 0) + 20,  # Score Hunter élevé
                        "source": "hunter.io_finder",
                        "confidence": email_data.get("confidence", 0),
                        "verification": email_data.get("verification", {}),
                        "position": email_data.get("position", ""),
                        "linkedin": email_data.get("linkedin_url", ""),
                        "twitter": email_data.get("twitter", "")
                    })
                    print(f"  🎯 Email Finder: {email_data['email']} (score: {email_data.get('score', 0)})")
        
        # 2) Domain Search - tous les emails du domaine
        if domain:
            domain_url = f"{HUNTER_BASE_URL}/domain-search"
            params = {
                "domain": domain,
                "api_key": HUNTER_API_KEY,
                "limit": 50  # Augmenter la limite pour plus de résultats
            }
            
            response = requests.get(domain_url, params=params, timeout=10)
            print(f"  📡 Domain Search API call: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                for email_data in data.get("data", {}).get("emails", []):
                    # Filtrer par nom/prénom
                    email = email_data.get("value", "")
                    if (first_name.lower() in email.lower() or 
                        last_name.lower() in email.lower()):
                        emails_found.append({
                            "email": email,
                            "score": email_data.get("confidence", 0) + 15,
                            "source": "hunter.io_domain",
                            "confidence": email_data.get("confidence", 0),
                            "verification": email_data.get("verification", {}),
                            "position": email_data.get("position", ""),
                            "department": email_data.get("department", ""),
                            "seniority": email_data.get("seniority", "")
                        })
                        print(f"  🏢 Domain Search: {email}")
        
        # 3) Email Count - vérifier la disponibilité
        if domain:
            count_url = f"{HUNTER_BASE_URL}/email-count"
            params = {"domain": domain}
            
            response = requests.get(count_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                total_emails = data.get("data", {}).get("total", 0)
                print(f"  📊 Email Count: {total_emails} emails disponibles sur {domain}")
        
        # 4) Company Enrichment - informations sur l'entreprise
        if domain:
            company_url = f"{HUNTER_BASE_URL}/companies/find"
            params = {
                "domain": domain,
                "api_key": HUNTER_API_KEY
            }
            
            response = requests.get(company_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                company_data = data.get("data", {})
                print(f"  🏢 Company: {company_data.get('name', domain)}")
                print(f"  👥 Employees: {company_data.get('metrics', {}).get('employees', 'N/A')}")
                print(f"  🏭 Industry: {company_data.get('category', {}).get('industry', 'N/A')}")
        
        # 5) Author Finder - recherche par nom complet (sans domaine)
        author_url = f"{HUNTER_BASE_URL}/author-finder"
        params = {
            "first_name": first_name,
            "last_name": last_name,
            "api_key": HUNTER_API_KEY
        }
        if company:
            params["company"] = company
        
        response = requests.get(author_url, params=params, timeout=10)
        print(f"  📡 Author Finder API call: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            for email_data in data.get("data", []):
                email = email_data.get("email", "")
                if email:
                    emails_found.append({
                        "email": email,
                        "score": email_data.get("confidence", 0) + 12,
                        "source": "hunter.io_author",
                        "confidence": email_data.get("confidence", 0),
                        "linkedin": email_data.get("linkedin_url", ""),
                        "twitter": email_data.get("twitter", "")
                    })
                    print(f"  👤 Author Finder: {email}")
        
        # 6) Enrichissement pour chaque email trouvé
        for email_entry in emails_found:
            email = email_entry["email"]
            enrich_url = f"{HUNTER_BASE_URL}/people/find"
            params = {
                "email": email,
                "api_key": HUNTER_API_KEY
            }
            
            try:
                response = requests.get(enrich_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    person_data = data.get("data", {})
                    # Enrichir les données
                    email_entry.update({
                        "full_name": person_data.get("name", {}).get("fullName", ""),
                        "location": person_data.get("location", ""),
                        "bio": person_data.get("bio", ""),
                        "company_name": person_data.get("employment", {}).get("name", ""),
                        "job_title": person_data.get("employment", {}).get("title", ""),
                        "github": person_data.get("github", {}).get("handle", ""),
                        "phone": person_data.get("phone", "")
                    })
                    print(f"  💎 Enriched: {email} -> {email_entry.get('full_name', 'N/A')}")
            except:
                pass  # Enrichment optionnel
        
        # Ajouter recherche dans les leaks de données
        leak_results = search_in_data_leaks(first_name, last_name)
        for leak_data in leak_results:
            emails_found.append({
                "email": leak_data["email"],
                "score": leak_data["score"],
                "source": f"data_leak_{leak_data['source']}",
                "confidence": 90,  # Haute confiance pour les leaks vérifiés
                "breach_date": leak_data.get("breach_date", ""),
                "data_types": leak_data.get("data_types", []),
                "verified_leak": leak_data.get("verified", False)
            })
            print(f"  💥 Leak trouvé: {leak_data['email']} dans {leak_data['source']}")
        
        # Recherche Phonebook.cz (gratuit)
        phonebook_results = phonebook_cz_search(first_name, last_name)
        emails_found.extend(phonebook_results)
        
    except Exception as e:
        print(f"  ❌ Erreur Hunter.io: {e}")
    
    return emails_found



def search_in_data_leaks(first_name, last_name):
    """Recherche dans plusieurs sources de fuites de données GRATUITES"""
    leak_results = []
    
    print(f"🔍 Recherche de fuites pour {first_name} {last_name}")
    
    # 1. Génération d'emails probables
    potential_emails = generate_email_variations(first_name, last_name)
    
    # Limiter à 8 emails les plus probables pour éviter rate limiting
    priority_emails = potential_emails[:8]
    
    for email in priority_emails:
        print(f"  🔎 Test: {email}")
        
        # HIBP check (gratuit)
        hibp_results = haveibeenpwned_check(email)
        for breach in hibp_results:
            leak_results.append({
                "email": email,
                "score": 25,
                "source": f"hibp_{breach.get('Name', 'unknown')}",
                "breach_date": breach.get("BreachDate", ""),
                "data_types": breach.get("DataClasses", []),
                "verified": breach.get("IsVerified", False)
            })
        
        # LeakCheck.io check 
        leakcheck_result = leakcheck_io_search(email)
        if leakcheck_result:
            leak_results.append(leakcheck_result)
        
        # EmailRep.io check 
        emailrep_result = emailrep_io_check(email)
        if emailrep_result:
            leak_results.append(emailrep_result)
        
        time.sleep(1.2)  
    
    # 2. Recherche dans Pastebin et sites similaires
    paste_results = search_paste_sites(first_name, last_name)
    leak_results.extend(paste_results)
    
    # 3. Recherche dans archives web
    archive_results = search_web_archives(first_name, last_name)
    leak_results.extend(archive_results)
    
    # 4. Recherche sur Phonebook.cz (déjà implémenté)
    phonebook_results = phonebook_cz_search(first_name, last_name)
    for result in phonebook_results:
        result["score"] = 20  # Score pour source OSINT
        result["source"] = "phonebook_cz_leak"
    leak_results.extend(phonebook_results)
    
    # 5. Recherche IntelX (API publique limitée)
    intelx_results = search_intelx_public(first_name, last_name)
    leak_results.extend(intelx_results)
    
    print(f"  💥 Total leaks trouvés: {len(leak_results)}")
    return leak_results

def emailrep_io_check(email):
    """EmailRep.io - API gratuite pour réputation email"""
    try:
        url = f"https://emailrep.io/{email}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            
            # Vérifier si l'email a une mauvaise réputation (indicateur de leak)
            reputation = data.get("reputation", "none")
            suspicious = data.get("suspicious", False)
            malicious = data.get("malicious", False)
            
            if suspicious or malicious or reputation == "low":
                print(f"  ⚠️ EmailRep: {email} - Réputation suspecte")
                return {
                    "email": email,
                    "score": 18,
                    "source": "emailrep_io",
                    "breach_date": "",
                    "data_types": ["reputation"],
                    "verified": False,
                    "reputation": reputation,
                    "suspicious": suspicious,
                    "malicious": malicious,
                    "details": data.get("details", {})
                }
        
        print(f"  ✅ EmailRep: {email} - Réputation OK")
        return None
        
    except Exception as e:
        print(f"  ❌ Erreur EmailRep: {e}")
        return None

def search_paste_sites(first_name, last_name):
    """Recherche dans les sites de paste publics GRATUITS"""
    results = []
    
    # Sites avec recherche publique gratuite
    paste_sites = [
        {
            "name": "pastebin",
            "url": "https://pastebin.com/search?q={query}",
            "enabled": True
        },
        {
            "name": "justpaste",
            "url": "https://justpaste.it/search?query={query}",
            "enabled": True
        },
        {
            "name": "ghostbin",
            "url": "https://ghostbin.co/search?q={query}",
            "enabled": False  
        }
    ]
    
    queries = [
        f'"{first_name} {last_name}" "@"',
        f'{first_name} {last_name} email',
        f'{first_name}.{last_name}@'
    ]
    
    for site in paste_sites:
        if not site["enabled"]:
            continue
            
        for query in queries:
            try:
                url = site["url"].format(query=quote(query))
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
                
                print(f"  🔍 Recherche {site['name']}: {query}")
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    # Extraction d'emails du HTML
                    emails = set(EMAIL_REGEX.findall(response.text))
                    
                    for email in emails:
                        # Filtrer par nom/prénom
                        if (first_name.lower() in email.lower() or 
                            last_name.lower() in email.lower()):
                            results.append({
                                "email": email,
                                "score": 15,
                                "source": f"paste_{site['name']}",
                                "breach_date": "",
                                "data_types": ["paste"],
                                "verified": False,
                                "query_used": query
                            })
                            print(f"    💥 Email trouvé: {email}")
                
                time.sleep(3)  
                
            except Exception as e:
                print(f"  ⚠️ Erreur {site['name']}: {e}")
    
    return results

def search_web_archives(first_name, last_name):
    """Recherche dans les archives web GRATUITES"""
    results = []
    
    try:
        # 1. Archive.org Wayback Machine API
        queries = [
            f'"{first_name} {last_name}" email',
            f'{first_name}.{last_name}@',
            f'{first_name} {last_name} contact'
        ]
        
        for query in queries:
            try:
                # Recherche dans les URLs archivées
                search_url = f"https://web.archive.org/cdx/search/cdx"
                params = {
                    "url": "*",
                    "output": "json",
                    "filter": "statuscode:200",
                    "collapse": "urlkey",
                    "limit": "20",
                    "matchType": "prefix",
                    "fl": "timestamp,original,urlkey,digest",
                }
                
                response = requests.get(search_url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    
                    # Analyser les URLs archivées pertinentes
                    for entry in data[1:]:  # Skip header
                        if len(entry) >= 2:
                            timestamp, original_url = entry[0], entry[1]
                            
                            # Filtrer les URLs pertinentes
                            if any(keyword in original_url.lower() for keyword in [
                                'contact', 'about', 'team', 'staff', 'directory'
                            ]):
                                # Construire l'URL archivée
                                archived_url = f"https://web.archive.org/web/{timestamp}/{original_url}"
                                
                                # Scraper l'archive pour emails
                                archive_emails = scrape_archived_page(archived_url, first_name, last_name)
                                
                                for email in archive_emails:
                                    results.append({
                                        "email": email,
                                        "score": 20,
                                        "source": "wayback_machine",
                                        "breach_date": timestamp[:8],  # YYYYMMDD
                                        "data_types": ["archive"],
                                        "verified": False,
                                        "archived_url": archived_url,
                                        "original_url": original_url
                                    })
                                
                                time.sleep(2)  # Délai entre archives
                                if len(results) >= 10:  # Limiter les résultats
                                    break
                
                time.sleep(3)
                
            except Exception as e:
                print(f"  ⚠️ Erreur Archive.org query: {e}")
        
        # 2. Archive.today (archive.ph)
        try:
            search_query = f"{first_name} {last_name}"
            archive_today_url = f"https://archive.today/search/?q={quote(search_query)}"
            
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            response = requests.get(archive_today_url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                # Simple extraction d'emails de la page de résultats
                emails = set(EMAIL_REGEX.findall(response.text))
                for email in emails:
                    if (first_name.lower() in email.lower() or 
                        last_name.lower() in email.lower()):
                        results.append({
                            "email": email,
                            "score": 18,
                            "source": "archive_today",
                            "breach_date": "",
                            "data_types": ["archive"],
                            "verified": False
                        })
            
        except Exception as e:
            print(f"  ⚠️ Erreur Archive.today: {e}")
            
    except Exception as e:
        print(f"  ❌ Erreur recherche archives: {e}")
    
    return results

def scrape_archived_page(archived_url, first_name, last_name):
    """Scrape une page archivée pour extraire des emails"""
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        response = requests.get(archived_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            emails = set(EMAIL_REGEX.findall(response.text))
            
            # Filtrer par nom/prénom
            relevant_emails = []
            for email in emails:
                if (first_name.lower() in email.lower() or 
                    last_name.lower() in email.lower()):
                    relevant_emails.append(email)
                    print(f"    📧 Archive email: {email}")
            
            return relevant_emails
        
    except Exception as e:
        print(f"  ⚠️ Erreur scraping archive: {e}")
    
    return []

def search_intelx_public(first_name, last_name):
    """IntelX recherche publique limitée (GRATUIT)"""
    results = []
    
    try:
        # IntelX a une interface publique limitée
        query = f"{first_name} {last_name}"
        url = f"https://intelx.io/tools?tab=search"
        
        
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        
        # Simuler une recherche publique basique
        search_data = {
            "term": query,
            "maxresults": 10,
            "timeout": 30,
            "sort": 4,  # Sort by date
            "media": 0,  # All media types
        }
        
        
        print(f"  ℹ️ IntelX: Recherche publique limitée pour {query}")
        
    except Exception as e:
        print(f"  ⚠️ IntelX non disponible: {e}")
    
    return results

def search_github_commits_emails(first_name, last_name):
    """Recherche d'emails dans les commits GitHub publics"""
    results = []
    
    try:
        # GitHub Search API (publique, limitée)
        query = f"{first_name} {last_name} in:file filename:package.json OR filename:setup.py"
        url = f"https://api.github.com/search/code?q={quote(query)}"
        
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            for item in data.get("items", []):
                # Récupérer le contenu du fichier
                file_url = item.get("url", "")
                if file_url:
                    file_resp = requests.get(file_url, headers=headers, timeout=10)
                    if file_resp.status_code == 200:
                        file_data = file_resp.json()
                        content = file_data.get("content", "")
                        
                        

                        try:
                            decoded_content = base64.b64decode(content).decode('utf-8')
                            emails = set(EMAIL_REGEX.findall(decoded_content))
                            
                            for email in emails:
                                if (first_name.lower() in email.lower() or 
                                    last_name.lower() in email.lower()):
                                    results.append({
                                        "email": email,
                                        "score": 22,
                                        "source": "github_public",
                                        "breach_date": "",
                                        "data_types": ["code"],
                                        "verified": False,
                                        "repo": item.get("repository", {}).get("full_name", ""),
                                        "file": item.get("name", "")
                                    })
                                    print(f"    💻 GitHub email: {email}")
                        except:
                            pass
                
                time.sleep(1)  
                
        elif response.status_code == 403:
            print(f"  ⚠️ GitHub: Rate limit atteint")
        
    except Exception as e:
        print(f"  ⚠️ Erreur GitHub: {e}")
    
    return results


def search_in_data_leaks(first_name, last_name):
    """Version complète avec toutes les sources gratuites"""
    leak_results = []
    
    print(f"🔍 Recherche COMPLÈTE de fuites pour {first_name} {last_name}")
    
    # 1. APIs gratuites pour emails probables
    potential_emails = generate_email_variations(first_name, last_name)
    priority_emails = potential_emails[:8]
    
    for email in priority_emails:
        print(f"  🔎 Test: {email}")
        
        # HIBP (gratuit)
        hibp_results = haveibeenpwned_check(email)
        for breach in hibp_results:
            leak_results.append({
                "email": email,
                "score": 25,
                "source": f"hibp_{breach.get('Name', 'unknown')}",
                "breach_date": breach.get("BreachDate", ""),
                "data_types": breach.get("DataClasses", []),
                "verified": breach.get("IsVerified", False)
            })
        
        # LeakCheck.io 
        leakcheck_result = leakcheck_io_search(email)
        if leakcheck_result:
            leak_results.append(leakcheck_result)
        
        # EmailRep.io 
        emailrep_result = emailrep_io_check(email)
        if emailrep_result:
            leak_results.append(emailrep_result)
        
        time.sleep(1.2)
    
    # 2. Recherche dans pastes publics
    paste_results = search_paste_sites(first_name, last_name)
    leak_results.extend(paste_results)
    
    # 3. Archives web
    archive_results = search_web_archives(first_name, last_name)
    leak_results.extend(archive_results)
    
    # 4. Phonebook.cz OSINT
    phonebook_results = phonebook_cz_search(first_name, last_name)
    for result in phonebook_results:
        result["score"] = 20
        result["source"] = "phonebook_cz_osint"
    leak_results.extend(phonebook_results)
    
    # 5. GitHub commits publics
    github_results = search_github_commits_emails(first_name, last_name)
    leak_results.extend(github_results)
    
    print(f"  💥 Total sources vérifiées: {len(leak_results)}")
    return leak_results


def get_random_proxy_and_ua():
    """Retourne un proxy et user-agent aléatoires"""
    proxy = random.choice(PROXY_POOL) if PROXY_POOL else None
    ua = random.choice(USER_AGENTS)
    return proxy, ua

# 2) Respect des robots.txt
def get_robot_parser(base_url):
    """
    Renvoie un RobotFileParser. En cas d'erreur (URL invalide ou pas de robots.txt),
    on renvoie un parser permissif (autorise tout).
    """
    rp = RobotFileParser()
    try:
        robots_url = urljoin(base_url, "/robots.txt")
        rp.set_url(robots_url)
        rp.read()
    except Exception:
        
        rp.parse([])  
    return rp

def get_delay(rp):
    cd = rp.crawl_delay(USER_AGENT)
    return cd if cd is not None else random.uniform(2, 5)

# 3) Construction dynamique des requêtes
GOOGLE_OPS = [
    '""', 'OR', '|', '()', '-', '*', '#..#', '$', '€',
    'in', '~', '+', 'daterange:', 'link:', 'inanchor:', 'allinanchor:',
    'inposttitle:', 'cache:', 'filetype:', 'ext:', 'site:', 'related:',
    'intitle:', 'allintitle:', 'inurl:', 'allinurl:', 'intext:', 'allintext:',
    'AROUND({n})', 'weather:', 'stocks:', 'map:', 'movie:', 'source:', '_',
    'blogurl:', 'loc:', 'location:', 'info:', 'near', 'type:', 'owner:',
    'after:', 'before:', 'to:', 'title:', 'source:domain', 'is:trashed',
    'is:starred', 'from:', 'cc:', 'bcc:', 'subject:', '{}', 'has:attachment',
    'has:drive', 'has:document', 'has:youtube', 'list:', 'filename:',
    'in:anywhere', 'is:important', 'label:', 'is:snoozed', 'is:unread',
    'is:read', 'has:yellow-star', 'has:blue-info', 'older:', 'newer:',
    'is:chat', 'deliveredto:', 'category:', 'size:', 'larger:', 'smaller:',
    'has:userlabels'
]

SEARCH_ENGINES = {
    "google":   "https://www.google.com/search?q={q}",
    "bing":     "https://www.bing.com/search?q={q}",
    "duckduck": "https://html.duckduckgo.com/html?q={q}"
}

def build_queries(profile, domain_required=True, mode="complete"):
    """
    Génère les requêtes selon le mode choisi:
    - quick: ~2-5 min (requêtes essentielles + sites de données)
    - medium: ~10-15 min (50 requêtes ciblées) 
    - complete: ~30-60 min (100+ requêtes exhaustives)
    """
    prenom, nom, domaine = profile.get("prenom"), profile.get("nom"), profile.get("domaine", "")
    full = f'"{prenom} {nom}"'
    ops = []

    
    if mode == "quick":
        ops += [
            full,
            f'{full} email',
            f'"{prenom} {nom}" contact',
            f'"{prenom} {nom}" "@"',
            # Sites sociaux principaux
            f'site:linkedin.com "{prenom} {nom}"',
            f'site:github.com "{prenom} {nom}"',
            f'site:twitter.com "{prenom} {nom}"',
            f'site:facebook.com "{prenom} {nom}"',
            # Sites de données/OSINT essentiels
            f'site:phonebook.cz "{prenom} {nom}"',
            f'site:hunter.io "{prenom} {nom}"',
            f'site:archive.org "{prenom} {nom}"',
            f'site:pastebin.com "{prenom} {nom}" "@"',
            f'site:societe.com "{prenom} {nom}"',
            f'site:infogreffe.fr "{prenom} {nom}"'
        ]
        return list(dict.fromkeys(ops))

    # MOYEN: requêtes ciblées
    elif mode == "medium":
        ops += [
            full,
            f'{full} AROUND(5) email',
            f'{full} contact',
            f'{full} "@"'
        ]
        
        # Sites principaux seulement
        main_sites = [
            "linkedin.com", "github.com", "twitter.com", "facebook.com",
            "instagram.com", "medium.com", "dev.to", "stackoverflow.com"
        ]
        
        for site in main_sites:
            ops.append(f'site:{site} "{prenom} {nom}"')
            
        ops += [
            f'intitle:"{prenom} {nom}"',
            f'intext:"{prenom} {nom}" email',
            f'"{prenom} {nom}" profile'
        ]
        
        return list(dict.fromkeys(ops))

    # COMPLET: toutes les requêtes (code existant)
    else:
        ops += [
            full,
            f'{full} AROUND(5) email',
            f'{full} deliveredto:',
            f'{full} filetype:pdf',
            f'{full} filetype:doc OR filetype:docx'
        ]

        profile_sites = [
            "linkedin.com", "github.com", "twitter.com", "facebook.com", 
            "instagram.com", "youtube.com", "tiktok.com", "researchgate.net",
            "academia.edu", "orcid.org", "behance.net", "dribbble.com",
            "medium.com", "dev.to", "stackoverflow.com", "reddit.com",
            "pinterest.com", "tumblr.com", "vimeo.com", "soundcloud.com",
            "flickr.com", "500px.com", "deviantart.com", "artstation.com",
            "twitch.tv", "discord.gg", "telegram.org", "whatsapp.com",
            "snapchat.com", "about.me", "linktree.com", "carrd.co",
            "hunter.io", "phonebook.cz", "pipl.com", "spokeo.com",
            "haveibeenpwned.com", "dehashed.com", "emailrep.io",
            "archive.org", "pastebin.com", "infogreffe.fr", "societe.com"
        ]
        
        # requêtes spécifiques pour chaque site de profil
        for site in profile_sites:
            ops.append(f'site:{site} "{prenom} {nom}"')
            ops.append(f'site:{site} "{prenom}" "{nom}"')
            
        # requêtes pour détecter des profils
        ops += [
            f'"{prenom} {nom}" profile',
            f'"{prenom} {nom}" profil',
            f'"{prenom} {nom}" "member since"',
            f'"{prenom} {nom}" "joined"',
            f'"{prenom} {nom}" "user profile"',
            f'"{prenom} {nom}" "about me"',
            f'"{prenom} {nom}" "bio"',
        ]

        ops += [
            f'site:linkedin.com/in {full}',
            f'site:github.com {full}',
            f'site:researchgate.net {full}'
        ]

        for op in ["intitle:", "intext:", "inurl:", "allintext:", "allintitle:"]:
            ops.append(f'{op}{full}')

        # domain filtering
        if domain_required and domaine:
            ops = [f'site:{domaine} {q}' for q in ops]

        # forcer la présence du caractère @ (recherche d'e-mails)
        ops += [
            f'{full} "@"',
            f'{full} intext:"@"',
            f'{full} allintext:@"',
        ]

        ops += [
            f'{full} OR "{prenom}" OR "{nom}"',
            f'("{prenom}" AND "{nom}") -login -signup',
            f'"{prenom}" | "{nom}"',
            f'("{prenom}" "{nom}") AROUND(3) (CV OR résumé OR bio OR profil)'
        ]

        # intégrer quelques autres operators aléatoirement
        for sample_op in random.sample(GOOGLE_OPS, 5):
            if '{n}' in sample_op:
                sample_op = sample_op.format(n=3)
            ops.append(f'{sample_op} {full}')

        # Requêtes spécifiques pour les fuites de données et OSINT
        ops += [
            f'site:pastebin.com "{prenom} {nom}" "@"',
            f'site:archive.org "{prenom} {nom}" email',
            f'site:phonebook.cz "{prenom} {nom}"',
            f'site:hunter.io "{prenom} {nom}"',
            f'site:societe.com "{prenom} {nom}"',
            f'site:infogreffe.fr "{prenom} {nom}"',
            f'site:arxiv.org "{prenom} {nom}"',
            f'site:hal.archives-ouvertes.fr "{prenom} {nom}"',
            f'"data breach" "{prenom} {nom}" email',
            f'"leak" "{prenom} {nom}" "@"',
            f'"dump" "{prenom} {nom}" email'
        ]
        
        return list(dict.fromkeys(ops))  

# 4) Fonctions de scraping SERP
def extract_links_google(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    
    all_links = soup.find_all('a', href=True)
    print(f"    🔍 {len(all_links)} liens HTML trouvés au total")
    
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith("/url?q="):
            url = href.split("&")[0].replace("/url?q=", "")
            if not urlparse(url).netloc.endswith("google.com"):
                links.append(url)
                print(f"    ✅ Lien valide: {url}")
    
    
    print(f"    📝 Échantillon de liens bruts:")
    for i, link in enumerate(all_links[:3]):
        print(f"      {i+1}. {link.get('href', 'N/A')}")
        
    return links

def extract_links_bing(html):
    soup = BeautifulSoup(html, "html.parser")
    return [a['href'] for a in soup.select('li.b_algo h2 a') if a['href']]

def extract_links_duck(html):
    soup = BeautifulSoup(html, "html.parser")
    return [a['href'] for a in soup.find_all('a', {'class': 'result__a'}, href=True)]

def search_engine_links(engine, query):
    """Recherche avec debug amélioré"""
    url = SEARCH_ENGINES[engine].format(q=quote(query))
    print(f"  🌐 URL complète: {url}")
    
    resp = requests.get(url, headers=HEADERS, timeout=10)
    print(f"  📊 Status: {resp.status_code}, Taille: {len(resp.text)} chars")
    
    if resp.status_code != 200:
        return []
    html = resp.text
    
    # Debug: vérifier si Google bloque
    if "robots" in html.lower() or "captcha" in html.lower():
        print(f"  ⚠️ Possible blocage détecté dans la réponse")
    
    if engine == "google":
        links = extract_links_google(html)
        print(f"  🔗 {len(links)} liens extraits")
        return links
    if engine == "bing":
        return extract_links_bing(html)
    if engine == "duckduck":
        return extract_links_duck(html)
    return []

# 5) Extraction des emails sur une page
def scrape_emails_from_page(url):
    """Version améliorée avec support documents et JS"""
    proxy, ua = get_random_proxy_and_ua()
    headers = {"User-Agent": ua}
    proxies = {"http": proxy, "https": proxy} if proxy else None
    
    try:
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=10)
        html = resp.text if resp.status_code == 200 else ""
        
        # Si c'est un document, extraire le texte
        if any(url.endswith(f'.{ext}') for ext in DOCUMENT_TYPES):
            html = extract_text_from_document(url, resp.content)
        
        # Si contient du JavaScript, utiliser Selenium
        elif '<script src=' in html or 'data-reactroot' in html:
            js_emails = scrape_with_selenium(url)
            if js_emails:
                return js_emails
        
    except:
        return set()
   
    emails = {m.group() for m in EMAIL_REGEX.finditer(html)}
    delivered = {m[1] for m in DELIVEREDTO_REGEX.finditer(html)}
    return emails.union(delivered)

def scrape_with_selenium(url):
    """Scrape JavaScript avec Selenium pour contenu dynamique"""
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    try:
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(3)  # Attendre le JS
        html = driver.page_source
        driver.quit()
        
        emails = {m.group() for m in EMAIL_REGEX.finditer(html)}
        return emails
    except Exception as e:
        print(f"  ⚠️ Erreur Selenium: {e}")
        return set()

def extract_text_from_document(url, content):
    """Extract texte de documents PDF/DOC/etc."""
    try:
        if url.endswith('.pdf'):
            pdf_reader = PyPDF2.PdfReader(BytesIO(content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text()
            return text
        elif url.endswith(('.doc', '.docx', '.ppt', '.pptx')):
            return textract.process(BytesIO(content)).decode('utf-8')
        else:
            return content.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  ⚠️ Erreur extraction document: {e}")
        return ""

async def async_search_engine(session, engine, query, proxy=None):
    """Recherche asynchrone sur un moteur"""
    url = SEARCH_ENGINES[engine].format(q=quote(query))
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    
    try:
        proxy_url = proxy if proxy else None
        async with session.get(url, headers=headers, proxy=proxy_url, timeout=10) as resp:
            if resp.status == 200:
                html = await resp.text()
                if engine == "google":
                    return extract_links_google(html)
                elif engine == "bing":
                    return extract_links_bing(html)
    except Exception as e:
        print(f"  ⚠️ Erreur async {engine}: {e}")
    return []

async def parallel_search(queries, engines_to_use, prenom, nom):
    """Recherche parallèle asynchrone"""
    connector = aiohttp.TCPConnector(limit=50)
    timeout = aiohttp.ClientTimeout(total=30)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        
        for q in queries:
            for engine in engines_to_use:
                if engine in SEARCH_ENGINES:
                    proxy, _ = get_random_proxy_and_ua()
                    task = async_search_engine(session, engine, q, proxy)
                    tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_links = set()
        for result in results:
            if isinstance(result, list):
                all_links.update(result)
        
        return list(all_links)

def score_email(email, source_url, context=""):
    """Score de confiance pour un email"""
    score = 0
    
    # Source officielle = score élevé
    if any(official in source_url for official in ['infogreffe.fr', 'societe.com', 'journal-officiel']):
        score += 10
    elif any(prof in source_url for prof in ['linkedin.com', 'github.com']):
        score += 8
    elif 'pastebin.com' in source_url:
        score += 3
    
    # Contexte autour de l'email
    if any(keyword in context.lower() for keyword in ['contact', 'email', 'mailto']):
        score += 5
    
    return score

# 6) Workflow principal
def categorize_site(domain):
    """Catégorise le type de site basé sur le domaine"""
    social_networks = [
        "facebook.com", "twitter.com", "instagram.com", "linkedin.com", 
        "youtube.com", "tiktok.com", "snapchat.com", "pinterest.com",
        "discord.com", "reddit.com", "telegram.org", "whatsapp.com",
        "clubhouse.com", "meetup.com", "badoo.com", "tinder.com",
        "happn.com", "bumble.com", "meetic.fr", "adopteunmec.com"
    ]
    
    professional = [
        "linkedin.com", "github.com", "stackoverflow.com", "researchgate.net", 
        "academia.edu", "orcid.org", "behance.net", "dribbble.com",
        "freelancer.com", "upwork.com", "fiverr.com", "malt.fr",
        "viadeo.com", "glassdoor.fr", "indeed.fr", "pole-emploi.fr",
        "apec.fr", "monster.fr", "regionsjob.com", "cadreemploi.fr"
    ]
    
    blogging = [
        "medium.com", "dev.to", "tumblr.com", "blogger.com", "wordpress.com",
        "skyrock.com", "over-blog.com", "canalblog.com", "centerblog.net",
        "eklablog.com", "overblog.com", "hautetfort.com"
    ]
    
    multimedia = [
        "youtube.com", "vimeo.com", "soundcloud.com", "flickr.com", "500px.com",
        "spotify.com", "deezer.com", "dailymotion.com", "twitch.tv",
        "netflix.com", "primevideo.com", "disneyplus.com", "mycanal.fr",
        "arte.tv", "france.tv", "6play.fr", "tf1.fr", "m6.fr"
    ]
    
    e_commerce = [
        "amazon.fr", "cdiscount.com", "fnac.com", "darty.com", "boulanger.com",
        "leclerc.com", "carrefour.fr", "auchan.fr", "intermarche.com",
        "monoprix.fr", "zalando.fr", "h&m.com", "zara.com", "lacoste.com",
        "decathlon.fr", "go-sport.com", "intersport.fr", "castorama.fr",
        "leroy-merlin.fr", "ikea.com", "conforama.fr", "but.fr"
    ]
    
    data_leaks_osint = [
        # Sites de leak de données publiques
        "haveibeenpwned.com", "dehashed.com", "leakcheck.io", "weleakinfo.to",
        "breachdirectory.org", "snusbase.com", "leak-lookup.com", "ghostproject.fr",
        
        # OSINT et recherche publique
        "hunter.io", "phonebook.cz", "intelx.io", "emailrep.io",
        "pipl.com", "spokeo.com", "whitepages.com", "truepeoplesearch.com",
        "fastpeoplesearch.com", "thatsthem.com", "beenverified.com",
        
        # Archives et caches
        "archive.org", "web.archive.org", "archive.today", "archive.ph",
        "cached.org", "cachedview.com",
        
        # Forums et sites communautaires où les emails peuvent apparaître
        "pastebin.com", "paste.ee", "justpaste.it", "hastebin.com",
        "dpaste.org", "ghostbin.co", "0bin.net",
        
        # Sites académiques et publications
        "arxiv.org", "hal.archives-ouvertes.fr", "tel.archives-ouvertes.fr",
        "theses.fr", "sudoc.abes.fr",
        
        # Registres publics et bases légales
        "infogreffe.fr", "societe.com", "verif.com", "pappers.fr",
        "bodacc.fr", "journal-officiel.gouv.fr",
        
        # Sites de CV et recrutement où les emails peuvent être visibles
        "cvtheque.regionsjob.com", "doyoubuzz.com", "viaduc.fr"
    ]
    
    news_media = [
        "lemonde.fr", "lefigaro.fr", "liberation.fr", "leparisien.fr",
        "20minutes.fr", "bfmtv.com", "franceinfo.fr", "rtl.fr",
        "europe1.fr", "rmc.bfmtv.com", "ouest-france.fr", "sudouest.fr",
        "ladepeche.fr", "nicematin.com", "lesechos.fr", "challenges.fr"
    ]
    
    government_services = [
        "service-public.fr", "ameli.fr", "caf.fr", "pole-emploi.fr",
        "impots.gouv.fr", "ants.gouv.fr", "laposte.fr", "urssaf.fr",
        "msa.fr", "cnav.fr", "education.gouv.fr", "enseignementsup-recherche.gouv.fr"
    ]
    
    gaming = [
        "steam.com", "epicgames.com", "ubisoft.com", "ea.com",
        "blizzard.com", "riot.com", "nintendo.fr", "playstation.com",
        "xbox.com", "jeuxvideo.com", "millenium.org", "gamekult.com"
    ]
    
    banking_finance = [
        "bnpparibas.net", "creditagricole.fr", "societegenerale.fr",
        "lcl.fr", "banquepopulaire.fr", "caisse-epargne.fr",
        "labanquepostale.fr", "creditmutuel.fr", "boursorama.com",
        "fortuneo.fr", "ing.fr", "monabanq.com"
    ]
    
    travel_transport = [
        "booking.com", "airbnb.fr", "expedia.fr", "tripadvisor.fr",
        "hotels.com", "sncf-connect.com", "blablacar.fr", "uber.com",
        "ryanair.com", "easyjet.com", "airfrance.fr"
    ]
    
    education = [
        "education.gouv.fr", "enseignementsup-recherche.gouv.fr",
        "cned.fr", "cnam.fr", "openclassrooms.com", "coursera.org",
        "edx.org", "udemy.com", "khan-academy.org"
    ]
    
    if any(sn in domain for sn in social_networks):
        return "Social"
    elif any(prof in domain for prof in professional):
        return "Professional"
    elif any(blog in domain for blog in blogging):
        return "Blog/Media"
    elif any(media in domain for media in multimedia):
        return "Multimedia"
    elif any(ecom in domain for ecom in e_commerce):
        return "E-commerce"
    elif any(leak in domain for leak in data_leaks_osint):
        return "Data/OSINT"
    elif any(news in domain for news in news_media):
        return "News/Media"
    elif any(gov in domain for gov in government_services):
        return "Government"
    elif any(game in domain for game in gaming):
        return "Gaming"
    elif any(bank in domain for bank in banking_finance):
        return "Banking/Finance"
    elif any(travel in domain for travel in travel_transport):
        return "Travel/Transport"
    elif any(edu in domain for edu in education):
        return "Education"
    else:
        return "Other"

def find_profiles(profiles, domain_required=True, mode="medium"):
    """
    TEMPS ESTIMÉ:
    - quick: 2-5 min par profil (8 requêtes × 2 moteurs × 2s = ~32s + scraping)
    - medium: 10-15 min par profil (~25 requêtes × 2 moteurs × 2s = ~100s + scraping)
    - complete: 30-60 min par profil (~100 requêtes × 3 moteurs × 2s = ~600s + scraping)
    """
    print(f"🚀 Mode: {mode.upper()}")
    
    if mode == "quick":
        print("⏱️ Temps estimé: 30 secondes - 2 min par profil (Hunter.io + HIBP + Phonebook)")
        engines_to_use = []  # Aucun moteur de recherche en mode quick
        max_links_to_visit = 0
    elif mode == "medium":
        print("⏱️ Temps estimé: 10-15 min par profil")
        engines_to_use = ["google", "bing"]
        max_links_to_visit = 25
    else:  # complete
        print("⏱️ Temps estimé: 30-60 min par profil")
        engines_to_use = ["google", "bing", "duckduck"]
        max_links_to_visit = None  # Pas de limite

    results = {}
    start_time = time.time()

    for profile in profiles:
        profile_start = time.time()
        prenom = profile["prenom"]
        nom = profile["nom"]
        domaine = profile.get("domaine", "")
        key = f"{prenom}_{nom}".lower()

        results[key] = {"links": set(), "emails": set(), "scored_emails": []}

        # 0) Recherche Hunter.io en priorité (rapide et fiable)
        if HUNTER_API_KEY:
            print(f"🎯 Recherche COMPLÈTE (Hunter.io + OSINT gratuit) pour {prenom} {nom}...")
            
            # Essayer plusieurs domaines courants si aucun fourni
            domains_to_try = []
            if domaine:
                domains_to_try.append(domaine)
            else:
                # Domaines courants français/internationaux
                common_domains = [
                    "gmail.com", "outlook.com", "yahoo.fr", "orange.fr", "free.fr",
                    "wanadoo.fr", "laposte.net", "sfr.fr", "hotmail.fr", "live.fr"
                ]
                domains_to_try.extend(common_domains[:3])  # Limiter à 3 pour éviter spam
            
            all_hunter_emails = []
            for test_domain in domains_to_try:
                print(f"  🔍 Test domaine: {test_domain}")
                hunter_emails = hunter_io_search(prenom, nom, test_domain, None)
                all_hunter_emails.extend(hunter_emails)
            
            # Aussi essayer Author Finder sans domaine
            hunter_emails_no_domain = hunter_io_search(prenom, nom, None, None)
            all_hunter_emails.extend(hunter_emails_no_domain)
            
            # Dédupliquer par email
            seen_emails = set()
            unique_hunter_emails = []
            for email_data in all_hunter_emails:
                if email_data["email"] not in seen_emails:
                    seen_emails.add(email_data["email"])
                    unique_hunter_emails.append(email_data)
            
            for hunter_data in unique_hunter_emails:
                results[key]["emails"].add(hunter_data["email"])
                results[key]["scored_emails"].append({
                    "email": hunter_data["email"],
                    "source": hunter_data["source"],
                    "score": hunter_data["score"],
                    "timestamp": time.time(),
                    "hunter_confidence": hunter_data.get("confidence", 0),
                    "verification": hunter_data.get("verification", {}),
                    "position": hunter_data.get("position", ""),
                    "company": hunter_data.get("company_name", ""),
                    "location": hunter_data.get("location", ""),
                    "linkedin": hunter_data.get("linkedin", ""),
                    "twitter": hunter_data.get("twitter", "")
                })
            
            # Génération d'emails probables même sans fuites
            print(f"🔮 Génération d'emails probables...")
            email_variations = generate_email_variations(prenom, nom)
            
            # Valider les emails générés avec Hunter.io et validation DNS
            valid_emails = []
            hunter_verified_emails = []
            
            print(f"  🔍 Validation de {min(15, len(email_variations))} emails probables...")
            
            for email in email_variations[:15] : # Limiter à 15 pour économiser l'API
                # Validation basique d'abord
                if not validate_email_format(email):
                    continue
                
                # Vérification Hunter.io pour les emails les plus probables
                if len(hunter_verified_emails) < 10:  # Limiter à 10 vérifications Hunter
                    hunter_result = hunter_verify_email(email)
                    if hunter_result:
                        hunter_verified_emails.append(hunter_result)
                        
                        # Ajouter à valid_emails selon le résultat Hunter
                        if hunter_result["result"] in ["deliverable", "risky"]:
                            valid_emails.append(email)
                            
                            # Ajouter directement aux résultats avec score Hunter
                            hunter_score = 15 + (hunter_result["score"] // 10)  # Score basé sur Hunter
                            if hunter_result["result"] == "deliverable":
                                hunter_score += 10
                            
                            results[key]["emails"].add(email)
                            results[key]["scored_emails"].append({
                                "email": email,
                                "source": "hunter_verified_probable",
                                "score": hunter_score,
                                "timestamp": time.time(),
                                "hunter_result": hunter_result["result"],
                                "hunter_score": hunter_result["score"],
                                "verification_details": hunter_result,
                                "method": "pattern_generation_verified"
                            })
                            print(f"    ✅ Email vérifié ajouté: {email} (Hunter: {hunter_result['result']})")
                        
                        time.sleep(0.5)  # Délai entre vérifications Hunter
            
            print(f"  📧 {len(valid_emails)} emails probables générés")
            print(f"  🔍 {len(hunter_verified_emails)} emails vérifiés par Hunter.io")
            
            # Recherche sur réseaux sociaux
            social_results = search_social_media(prenom, nom)
            for social in social_results:
                results[key]["scored_emails"].append({
                    "platform": social["platform"],
                    "profile": social["profile"],
                    "score": social["score"],
                    "timestamp": time.time(),
                    "type": "social_profile"
                })
            
            # Vérifier les emails probables avec HIBP 
            probable_emails = valid_emails + [
                f"{prenom.lower()}.{nom.lower()}@gmail.com",
                f"{prenom.lower()}{nom.lower()}@gmail.com", 
                f"{prenom.lower()}.{nom.lower()}@outlook.com",
                f"{prenom.lower()}.{nom.lower()}@yahoo.fr"
            ]
            
            # Dédupliquer
            probable_emails = list(set(probable_emails))[:12]  # Réduire car on a déjà vérifié avec Hunter
            
            for test_email in probable_emails:
               # Skip si déjà vérifié par Hunter
                if any(h["email"] == test_email for h in hunter_verified_emails):
                    continue
               
                # HIBP check
                hibp_results = haveibeenpwned_check(test_email)
                if hibp_results:
                    for breach in hibp_results:
                        results[key]["emails"].add(test_email)
                        results[key]["scored_emails"].append({
                            "email": test_email,
                            "source": f"hibp_{breach.get('Name', 'unknown')}",
                            "score": 30,  # Score élevé pour les leaks confirmés
                            "timestamp": time.time(),
                            "breach_date": breach.get("BreachDate", ""),
                            "data_classes": breach.get("DataClasses", []),
                            "verified": breach.get("IsVerified", False)
                        })
                        print(f"  💥 Breach confirmé: {test_email} dans {breach.get('Name')}")
                    continue  # Si trouvé dans HIBP, pas besoin de tester LeakCheck
                
                # LeakCheck.io check
                leakcheck_result = leakcheck_io_search(test_email)
                if leakcheck_result:
                    results[key]["emails"].add(test_email)
                    results[key]["scored_emails"].append({
                        "email": test_email,
                        "source": "leakcheck_io",
                        "score": 25,
                        "timestamp": time.time(),
                        "sources_count": leakcheck_result.get("sources_count", 0)
                    })
                else:
                    # Si pas de leak trouvé, ajouter comme "probable" avec score faible
                    if test_email not in results[key]["emails"]:
                        results[key]["emails"].add(test_email)
                        results[key]["scored_emails"].append({
                            "email": test_email,
                            "source": "generated_probable",
                            "score": 3,  # Score encore plus faible car non vérifié
                            "timestamp": time.time(),
                            "confidence": "low",
                            "method": "pattern_generation"
                        })
                
                # Délai entre les requêtes pour éviter le rate limiting
                time.sleep(1.5)
            
            # Si mode quick et qu'on a trouvé des résultats
            if mode == "quick":
                total_found = len(results[key]["emails"])
                print(f"✅ Recherche COMPLÈTE: {total_found} email(s) trouvé(s)")
                
                # Afficher un résumé des méthodes
                leak_count = len([e for e in results[key]["scored_emails"] if "hibp" in e.get("source", "") or "leakcheck" in e.get("source", "")])
                hunter_verified_count = len([e for e in results[key]["scored_emails"] if e.get("source") == "hunter_verified_probable"])
                probable_count = len([e for e in results[key]["scored_emails"] if e.get("source") == "generated_probable"])
                
                print(f"  💥 Leaks confirmés: {leak_count}")
                print(f"  🔍 Hunter vérifiés: {hunter_verified_count}")
                print(f"  🔮 Emails probables: {probable_count}")
                
                # Skip le scraping Google pour gagner du temps
                results[key]["links"] = {}
                
                # Trier les emails par score
                results[key]["scored_emails"].sort(key=lambda x: x["score"], reverse=True)
                
                profile_time = time.time() - profile_start
                print(f"⏱️ Profil {prenom} {nom} traité en {profile_time:.1f}s (Hunter.io uniquement)")
                continue

        # 1) Génération des requêtes selon le mode
        queries = build_queries(profile, domain_required, mode)
        print(f"📋 {len(queries)} requêtes générées pour {prenom} {nom}")

        # 2) Recherche parallèle asynchrone
        print("🚀 Lancement recherche parallèle...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        all_links = loop.run_until_complete(
            parallel_search(queries, engines_to_use, prenom, nom)
        )
        loop.close()
        
        results[key]["links"].update(all_links)
        print(f"🔗 {len(all_links)} liens uniques trouvés")

        # 3) Limitation des liens à visiter selon le mode
        links_to_visit = list(results[key]["links"])
        if max_links_to_visit:
            links_to_visit = links_to_visit[:max_links_to_visit]
            print(f"🔗 Visite limitée à {max_links_to_visit} liens sur {len(results[key]['links'])}")

        # 4) Scraping parallèle des emails
        print("📧 Extraction emails en parallèle...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {
                executor.submit(scrape_emails_from_page, link): link 
                for link in links_to_visit 
                if link.lower().startswith(("http://", "https://"))
            }
            
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    emails = future.result()
                    if emails:
                        print(f"  ✅ {len(emails)} email(s) sur {url}")
                        for email in emails:
                            score = score_email(email, url)
                            results[key]["scored_emails"].append({
                                "email": email,
                                "source": url,
                                "score": score,
                                "timestamp": time.time()
                            })
                        results[key]["emails"].update(emails)
                except Exception as e:
                    print(f"  ❌ Erreur sur {url}: {e}")

        # convertir sets en listes pour sérialisation
        results[key]["links"]  = list(results[key]["links"])
        results[key]["emails"] = list(results[key]["emails"])
       
       # extraire et catégoriser les sites
        sites_found = {}
        for link in results[key]["links"]:
            domain = urlparse(link).netloc
            if domain:
                category = categorize_site(domain)
                if category not in sites_found:
                    sites_found[category] = set()
                sites_found[category].add(domain)
        
        # convertir en listes
        results[key]["sites"] = {cat: list(domains) for cat, domains in sites_found.items()}

        # Trier les emails par score
        results[key]["scored_emails"].sort(key=lambda x: x["score"], reverse=True)
        
        profile_time = time.time() - profile_start
        print(f"⏱️ Profil {prenom} {nom} traité en {profile_time:.1f}s")

    total_time = time.time() - start_time
    print(f"🏁 Temps total: {total_time:.1f}s ({total_time/60:.1f} min)")
    
    return results


def test_quick_mode():
    """Test des APIs gratuites et configuration"""
    print("🧪 TEST MODE QUICK")
    print("=" * 50)
    
    # Test 1: Vérification APIs
    print("1️⃣ Test des APIs gratuites:")
    test_email = "test@gmail.com"
    
    # HIBP
    hibp_result = haveibeenpwned_check(test_email)
    print(f"  HIBP: {'✅' if hibp_result is not None else '❌'}")
    
    # LeakCheck
    leak_result = leakcheck_io_search(test_email)
    print(f"  LeakCheck: {'✅' if leak_result is not None else '❌'}")
    
    # EmailRep
    emailrep_result = emailrep_io_check(test_email)
    print(f"  EmailRep: {'✅' if emailrep_result is not None else '❌'}")
    
    # Test 2: Hunter.io
    print("\n2️⃣ Test Hunter.io:")
    if HUNTER_API_KEY:
        hunter_test = hunter_io_search("John", "Doe", "gmail.com")
        print(f"  Hunter API: {'✅' if hunter_test else '❌'}")
    else:
        print("  Hunter API: ❌ Clé manquante")
    
    # Test 3: Génération d'emails
    print("\n3️⃣ Test génération emails:")
    variations = generate_email_variations("Jean", "Dupont")
    print(f"  Variations générées: {len(variations)}")
    print(f"  Exemples: {variations[:3]}")
    
    return True

def monitor_medium_mode():
    """Monitoring pour mode medium"""
    print("📊 MONITORING MODE MEDIUM")
    
    # Compteurs pour surveillance
    counters = {
        "google_requests": 0,
        "google_blocks": 0,
        "bing_requests": 0,
        "links_found": 0,
        "emails_extracted": 0,
        "api_errors": 0
    }
    
    # Log des erreurs fréquentes
    error_patterns = [
        "403 Forbidden",
        "429 Too Many Requests", 
        "captcha",
        "robots.txt",
        "blocked"
    ]
    
    return counters

def analyze_results(results, mode):
    """Analyse et validation des résultats"""
    
    for profile_key, data in results.items():
        print(f"\n📊 ANALYSE: {profile_key}")
        
        # Comptage par source
        sources = {}
        for email_data in data.get("scored_emails", []):
            source = email_data.get("source", "unknown")
            if source not in sources:
                sources[source] = 0
            sources[source] += 1
        
        print(f"  📧 Total emails: {len(data.get('emails', []))}")
        print(f"  🔗 Total liens: {len(data.get('links', []))}")
        print(f"  📊 Sources utilisées:")
        
        for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
            print(f"    - {source}: {count}")
        
        # Top 3 emails par score
        top_emails = sorted(
            data.get("scored_emails", []), 
            key=lambda x: x.get("score", 0), 
            reverse=True
        )[:3]
        
        print(f"  🏆 Top 3 emails:")
        for i, email_data in enumerate(top_emails, 1):
            email = email_data.get("email", "")
            score = email_data.get("score", 0)
            source = email_data.get("source", "")
            print(f"    {i}. {email} (score: {score}) - {source}")
        
        # Validation mode QUICK
        if mode == "quick":
            expected_sources = ["hunter.io", "hibp", "leakcheck", "emailrep", "generated_probable"]
            found_sources = list(sources.keys())
            
            print(f"  ✅ Sources attendues en QUICK:")
            for expected in expected_sources:
                found = any(expected in source for source in found_sources)
                print(f"    - {expected}: {'✅' if found else '❌'}")

def test_implementation():
    """Test progressif de l'implémentation"""
    
    # Profils de test (commencer simple)
    test_profiles = [
        # Test 1: Profil connu (résultats attendus)
        {"prenom": "Alexis", "nom": "Ohanian", "domaine": "reddit.com"},
        
        # Test 2: Profil générique français
        {"prenom": "Jean", "nom": "Dupont", "domaine": ""},
        
    ]
    
    modes = ["quick", "medium"]  # Éviter complete au début
    
    for mode in modes:
        print(f"\n🚀 TEST MODE: {mode.upper()}")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            # Test avec 1 seul profil d'abord
            results = find_profiles([test_profiles[0]], domain_required=False, mode=mode)
            
            # Analyse des résultats
            analyze_results(results, mode)
            
            execution_time = time.time() - start_time
            print(f"⏱️ Temps d'exécution: {execution_time:.1f}s")
            
            # Attendre avant mode suivant
            if mode == "quick":
                print("⏸️ Pause 10s avant mode medium...")
                time.sleep(10)
                
        except Exception as e:
            print(f"❌ ERREUR en mode {mode}: {e}")
            break
    
    print("\n✅ Tests terminés!")



if __name__ == "__main__":
    import sys
    
    # Test de configuration
    print(f"🔧 Configuration Hunter.io:")
    print(f"  🔑 API Key: {'✅ Configurée' if HUNTER_API_KEY else '❌ Manquante'}")
    print(f"  🌐 Base URL: {HUNTER_BASE_URL}")
    
    # Gestion des arguments
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Mode test complet
        print("\n🧪 LANCEMENT DES TESTS")
        test_quick_mode()
        print("\n" + "="*60)
        test_implementation()
        
    elif len(sys.argv) > 1 and sys.argv[1] == "debug":
        # Mode debug simple
        print("\n🔍 MODE DEBUG")
        test_quick_mode()
        
    else:
        # Mode normal
        mode = sys.argv[1] if len(sys.argv) > 1 else "quick"
        
        profils = [
           {"prenom": "Jean", "nom": "Dupond", "domaine": ""},
        ]
        
        print(f"🎯 Lancement en mode: {mode}")
        out = find_profiles(profils, domain_required=False, mode=mode)
        
        # Analyser automatiquement les résultats
        analyze_results(out, mode)
        
        for k, v in out.items():
            print(f"\n==> Résultats détaillés pour {k.replace('_', ' ')}")
            print("Liens :", len(v["links"]))
            print("Emails:", len(v["emails"]))
            for e in v["emails"]:
                print(" -", e)


    