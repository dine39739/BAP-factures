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

# --- Styles personnalisés ---
st.markdown("""
    <style>
    .main {
        background-color: #f4f4f9;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: #007bff;
        color: white;
    }
    .result-card {
        background-color: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- Base de données fictive pour la démonstration ---
MOCK_DATABASE = [
    {"proprietaire": "KONATE MAKHAN KHADY", "adresse": "163 BD ANATOLE FRANCE, SAINT DENIS", "lot": "0000010", "quotePart": "329/10000", "section": "CE", "plan": "21"},
    {"proprietaire": "VELENTEAN GRIGORE", "adresse": "22 RUE LABROUSTE, 75015 PARIS", "lot": "0000013", "quotePart": "425/10000", "section": "CE", "plan": "21"},
    {"proprietaire": "LOLO DOVI LAWSON AYEKU", "adresse": "69 AV DU PDT WILSON, ST DENIS", "lot": "0000069", "quotePart": "105/10000", "section": "CN", "plan": "32"},
    {"proprietaire": "LOLO DOVI LAWSON AYEKU", "adresse": "69 AV DU PDT WILSON, ST DENIS", "lot": "0000072", "quotePart": "10/10000", "section": "CN", "plan": "32"},
    {"proprietaire": "MARTIN PIERRE", "adresse": "45 AVENUE VICTOR HUGO, 75016 PARIS", "lot": "0000101", "quotePart": "55/10000", "section": "CE", "plan": "22"},
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
    
    # Implémentation simplifiée du retry/backoff
    for delay in [1, 2, 4]:
        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            time.sleep(delay)
        except Exception:
            time.sleep(delay)
    return "L'analyse automatique n'a pas pu être générée."

# --- Interface Utilisateur ---
st.title("Extracteur de Données de Propriété 📄✨")
st.write("Importez vos relevés PDF pour extraire les informations et obtenir une analyse intelligente.")

# Barre latérale pour les filtres
with st.sidebar:
    st.header("Filtres d'extraction")
    section = st.text_input("Section", placeholder="Ex: CE, CN").strip().upper()
    plans_raw = st.text_input("Numéro(s) de Plan", placeholder="Ex: 21, 32 (vide pour tous)")
    
    st.divider()
    st.info("Note: Dans cette version, l'extraction de texte PDF est simulée à partir d'une base de données interne basée sur les fichiers importés.")

# Zone de dépôt de fichiers
uploaded_files = st.file_uploader("Glissez vos fichiers PDF ici", type="pdf", accept_multiple_files=True)

if st.button("Lancer l'extraction et l'analyse"):
    if not section:
        st.error("Veuillez renseigner au moins la Section.")
    elif not uploaded_files:
        st.warning("Veuillez importer au moins un fichier PDF.")
    else:
        # 1. Simulation de l'extraction
        with st.status("Extraction des données des PDF...", expanded=True) as status:
            time.sleep(1.5)
            
            # Parsing des plans
            plan_list = [p.strip() for p in plans_raw.split(',')] if plans_raw else []
            
            # Filtrage
            results = [
                item for item in MOCK_DATABASE 
                if item['section'] == section and (not plan_list or item['plan'] in plan_list)
            ]
            
            status.update(label="Extraction terminée !", state="complete", expanded=False)

        if results:
            # 2. Affichage des résultats
            st.subheader(f"Résultats pour Section {section} {'- Plan(s) ' + ', '.join(plan_list) if plan_list else ''}")
            st.table(results)
            
            # 3. Analyse Gemini
            st.divider()
            st.subheader("🤖 Analyse Intelligente Gemini")
            with st.spinner("Gemini analyse les données..."):
                analysis = call_gemini_analysis(results)
                st.markdown(f"""
                <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #6f42c1;">
                    {analysis}
                </div>
                """, unsafe_allow_html=True)
                
            # Option de téléchargement
            csv = "Proprietaire;Adresse;Lot;Quote-part\n" + "\n".join([f"{r['proprietaire']};{r['adresse']};{r['lot']};{r['quotePart']}" for r in results])
            st.download_button("Télécharger les données (CSV)", csv, "extraction.csv", "text/csv")
            
        else:
            st.info(f"Aucune donnée trouvée dans les fichiers pour la section {section} et les plans spécifiés.")

# Footer
st.markdown("---")
st.caption("Application propulsée par Streamlit et Gemini 2.5 Flash")