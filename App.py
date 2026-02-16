import streamlit as st
import json
import time
import requests

# --- Configuration de la page ---
st.set_page_config(
    page_title="Extracteur de Relevés de Propriété",
    page_icon="📄",
    layout="wide"
)

# --- Base de données de simulation (Source de vérité actuelle) ---
# L'application pioche ici car l'extraction réelle de PDF nécessite des librairies spécifiques 
# installées sur le serveur.
MOCK_DATABASE = [
    # Données AS - Viry Chatillon (Votre document KADHIRAVAN)
    {"proprietaire": "KADHIRAVAN MARC & SARGOUNADEVY", "adresse": "19 RUE BURGER, 94190 VILLENEUVE ST GEORGES", "lot": "0000237", "quotePart": "53/10000", "section": "AS", "plan": "108"},
    {"proprietaire": "KADHIRAVAN MARC & SARGOUNADEVY", "adresse": "19 RUE BURGER, 94190 VILLENEUVE ST GEORGES", "lot": "0000001", "quotePart": "90/10000", "section": "AS", "plan": "108"},
    {"proprietaire": "KADHIRAVAN MARC & SARGOUNADEVY", "adresse": "19 RUE BURGER, 94190 VILLENEUVE ST GEORGES", "lot": "0000085", "quotePart": "64/10000", "section": "AS", "plan": "108"},
    
    # Données CE - Saint Denis (Exemple KONATE)
    {"proprietaire": "KONATE MAKHAN KHADY", "adresse": "163 BD ANATOLE FRANCE, SAINT DENIS", "lot": "0000010", "quotePart": "329/10000", "section": "CE", "plan": "21"},
    {"proprietaire": "VELENTEAN GRIGORE", "adresse": "22 RUE LABROUSTE, 75015 PARIS", "lot": "0000013", "quotePart": "425/10000", "section": "CE", "plan": "21"},
    
    # Données CN - Saint Denis (Exemple LAWSON)
    {"proprietaire": "LOLO DOVI LAWSON AYEKU", "adresse": "69 AV DU PDT WILSON, ST DENIS", "lot": "0000069", "quotePart": "105/10000", "section": "CN", "plan": "32"},
]

def call_gemini_analysis(data):
    """Appelle l'API Gemini pour analyser les données extraites."""
    api_key = "" # Fournie par l'environnement
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    system_prompt = (
        "Tu es un analyste de données immobilières expert. "
        "Synthétise ces données de relevés de propriété en français. "
        "Indique le nombre de lots, les propriétaires principaux et les points notables."
    )
    
    payload = {
        "contents": [{"parts": [{"text": json.dumps(data)}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]}
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        pass
    return "L'analyse automatique n'a pas pu être générée."

# --- Interface ---
st.title("Extracteur de Données de Propriété 📄✨")

st.warning("""
**Note Technique :** L'application est actuellement en mode 'Simulation'. 
Elle affiche les données correspondant à la **Section** saisie ci-dessous en les cherchant dans une base de test. 
Pour traiter n'importe quel nouveau PDF, il faudrait activer un module de lecture OCR (comme Tesseract ou PDFPlumber).
""")

with st.sidebar:
    st.header("Paramètres")
    section_search = st.text_input("Section à extraire", value="AS").strip().upper()
    plans_search = st.text_input("Plans (optionnel)", placeholder="Ex: 108")

uploaded_files = st.file_uploader("Importer les relevés (PDF)", type="pdf", accept_multiple_files=True)

if st.button("Lancer l'analyse"):
    if uploaded_files:
        with st.spinner(f"Recherche des données pour la section {section_search}..."):
            time.sleep(1) # Simulation du temps de calcul
            
            # Filtrage dynamique basé sur la saisie utilisateur
            results = [d for d in MOCK_DATABASE if d['section'] == section_search]
            
            if results:
                st.success(f"Données trouvées pour la section {section_search}")
                st.table(results)
                
                st.subheader("🤖 Analyse de l'IA")
                analysis = call_gemini_analysis(results)
                st.info(analysis)
            else:
                st.error(f"Aucune donnée enregistrée pour la section '{section_search}'. Essayez 'CE' ou 'CN'.")
    else:
        st.error("Veuillez d'abord importer un fichier PDF.")
