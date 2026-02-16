import streamlit as st
import json
import time
import requests
import pdfplumber
import re
import io

# --- Configuration de la page ---
st.set_page_config(
    page_title="Extracteur Réel de Relevés de Propriété",
    page_icon="📄",
    layout="wide"
)

# --- Fonctions d'Extraction Réelle ---

def clean_extracted_text(text):
    """Nettoie le texte des sauts de ligne inutiles pour faciliter la détection."""
    if not text:
        return ""
    # On garde les espaces mais on réduit les répétitions de sauts de ligne
    return re.sub(r'\n+', '\n', text)

def extract_data_from_pdf(pdf_file, target_section):
    """
    Extrait réellement les données d'un fichier PDF importé.
    Optimisé pour capturer les titulaires et adresses sur plusieurs lignes.
    """
    extracted_results = []
    
    with pdfplumber.open(pdf_file) as pdf:
        full_text_pages = []
        for page in pdf.pages:
            full_text_pages.append(page.extract_text() or "")
        
        raw_text = "\n".join(full_text_pages)
        
        # 1. Extraction des titulaires (Noms et Prénoms)
        # On cherche "Nom:" suivi du texte jusqu'au prochain champ ou saut de ligne double
        noms_found = re.findall(r"Nom:\s*([A-Z\s\-]+)", raw_text, re.IGNORECASE)
        prenoms_found = re.findall(r"Prénom:\s*([A-Z\s\-]+)", raw_text, re.IGNORECASE)
        
        unique_owners = []
        for n, p in zip(noms_found, prenoms_found):
            full_name = f"{n.strip()} {p.strip()}".replace('\n', ' ')
            if full_name not in unique_owners:
                unique_owners.append(full_name)
        
        titulaire = " & ".join(unique_owners) if unique_owners else "Non détecté"
        
        # 2. Extraction de l'adresse (souvent après le prénom ou sous "Adresse:")
        # On cherche le bloc adresse qui commence par "Adresse:" et finit avant "Droit réel" ou "Propriété"
        adresse_titulaire = "Non détectée"
        adresse_match = re.search(r"Adresse:\s*(.*?)(?=Droit réel|Propriété|Identification|Page|$)", raw_text, re.DOTALL | re.IGNORECASE)
        if adresse_match:
            # On nettoie les sauts de ligne pour avoir une adresse sur une seule ligne
            adresse_titulaire = adresse_match.group(1).replace('\n', ' ').strip()
            # On supprime les espaces multiples
            adresse_titulaire = re.sub(r'\s+', ' ', adresse_titulaire)

        # 3. Analyse ligne par ligne pour les lots
        lines = raw_text.split('\n')
        
        for i, line in enumerate(lines):
            # Detection de la section (ex: "AS" ou AS)
            # On cherche la section de manière isolée ou entre guillemets
            if re.search(rf'"{target_section}"|\b{target_section}\b', line):
                # On scanne les lignes environnantes pour trouver les mots clés LOT et la quote-part
                context = " ".join(lines[max(0, i-2):i+8])
                
                # Cherche les lots (ex: LOT 0000237) et les fractions (ex: 53/10000)
                # Regex adaptée à la structure du document : "LOT 0000237 53/10000"
                lots_found = re.findall(r"LOT\s*(\d+)\s*(\d+/\d+)", context)
                
                for lot_num, qp in lots_found:
                    # Évite les doublons de lots dans le même fichier
                    if not any(r['lot'] == lot_num for r in extracted_results):
                        extracted_results.append({
                            "proprietaire": titulaire,
                            "adresse": adresse_titulaire,
                            "lot": lot_num,
                            "quotePart": qp,
                            "section": target_section,
                            "plan": "Détecté"
                        })

    return extracted_results

def call_gemini_analysis(data):
    """Appelle l'API Gemini pour analyser les données extraites."""
    api_key = "" # Fournie par l'environnement
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent?key={api_key}"
    
    system_prompt = (
        "Tu es un analyste de données immobilières expert. "
        "Synthétise ces données de relevés de propriété en français. "
        "Fais un résumé des biens, des propriétaires et des quotes-parts."
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
    return "L'analyse intelligente n'est pas disponible pour le moment."

# --- Interface Streamlit ---

st.title("Extracteur Intelligent de Relevés (PDF Réel) 📄")

with st.sidebar:
    st.header("Filtrage")
    section_target = st.text_input("Section à extraire (ex: AS, CE)", value="AS").strip().upper()
    st.info(f"L'extracteur va scanner le document pour trouver la section {section_target}.")

uploaded_files = st.file_uploader("Chargez vos relevés de propriété (PDF)", type="pdf", accept_multiple_files=True)

if st.button("Analyser les documents"):
    if not uploaded_files:
        st.error("Veuillez charger au moins un fichier PDF.")
    else:
        all_data = []
        
        with st.status("Extraction des informations (Noms, Adresses, Lots)...", expanded=True) as status:
            for uploaded_file in uploaded_files:
                st.write(f"Analyse en profondeur de : {uploaded_file.name}...")
                data = extract_data_from_pdf(uploaded_file, section_target)
                all_data.extend(data)
            
            status.update(label="Extraction terminée !", state="complete", expanded=False)

        if all_data:
            st.success(f"Succès : {len(all_data)} lots extraits avec les informations de propriété.")
            
            # Affichage stylisé
            st.subheader("Données Extraites")
            st.table(all_data)
            
            st.subheader("🤖 Synthèse de l'IA")
            with st.spinner("Analyse par Gemini..."):
                analysis = call_gemini_analysis(all_data)
                st.info(analysis)
                
            csv = "Proprietaire;Adresse;Lot;Section;Quote-part\n" + "\n".join([f"{d['proprietaire']};{d['adresse']};{d['lot']};{d['section']};{d['quotePart']}" for d in all_data])
            st.download_button("Exporter en CSV", csv, "extraction_propriete.csv", "text/csv")
        else:
            st.error(f"Aucun lot trouvé pour la section '{section_target}'.")
            st.info("Note : Assurez-vous que la section demandée est bien écrite en majuscules dans le document (ex: AS).")

st.markdown("---")
st.caption("Version 2.2 - Amélioration de la capture multi-lignes des titulaires et adresses")
