def extract_owners_from_text(text):
    """
    Extrait tous les propriétaires/indivisaires - VERSION CORRIGÉE
    """
    owners = []
    
    # Pattern principal : capture Numéro propriétaire + Nom + Prénom + Adresse
    owner_pattern = re.compile(
        r"Numéro propriétaire\s*:\s*(\w+).*?" +
        r"Nom\s*:\s*([A-ZÀ-Ü\s\-]+?)\s+" +
        r"Prénom\s*:\s*([A-ZÀ-Ü\s\-]+?)" +
        r"(?:\s+Adresse\s*:\s*(.*?))?(?=Numéro propriétaire|Propriété|$)",
        re.DOTALL | re.IGNORECASE
    )
    
    for match in owner_pattern.finditer(text):
        numero = match.group(1).strip()
        nom = clean_text_segment(match.group(2))
        prenom = clean_text_segment(match.group(3))
        adresse_raw = match.group(4) if match.group(4) else ""
        adresse = clean_text_segment(adresse_raw) if adresse_raw else "Non détectée"
        full_name = f"{nom} {prenom}".strip()
        
        if full_name:
            owners.append({
                "name": full_name,
                "address": adresse,
                "numero": numero
            })
    
    # Pattern de secours si le premier échoue (sans numéro propriétaire)
    if not owners:
        alt_pattern = re.compile(
            r"Nom\s*:\s*([A-ZÀ-Ü\s\-]+?)\s+" +
            r"Prénom\s*:\s*([A-ZÀ-Ü\s\-]+?)" +
            r"(?:.*?Adresse\s*:\s*(.*?))?(?=Nom\s*:|Propriété|$)",
            re.DOTALL | re.IGNORECASE
        )
        
        for match in alt_pattern.finditer(text):
            nom = clean_text_segment(match.group(1))
            prenom = clean_text_segment(match.group(2))
            adresse_raw = match.group(3) if match.group(3) else ""
            adresse = clean_text_segment(adresse_raw) if adresse_raw else "Non détectée"
            full_name = f"{nom} {prenom}".strip()
            
            if full_name:
                owners.append({
                    "name": full_name,
                    "address": adresse,
                    "numero": "N/A"
                })
    
    return owners
