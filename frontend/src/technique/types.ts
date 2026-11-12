export type Materiel = {
  id: number
  code: string
  type: string
  type_libelle: string
  designation: string
  marque: string
  modele: string
  numero_serie: string
  immatriculation: string
  annee: number | null
  capacite: string
  activite: string
  activite_libelle: string
  site: number | ''
  site_nom: string
  emplacement: number | null
  emplacement_nom: string
  etat: string
  etat_libelle: string
  compteur_heures: string | null
  compteur_km: number | null
  observations: string
  ordres_ouverts: number
}
export type Ordre = {
  id: number
  numero: string
  statut: string
  statut_libelle: string
  cree_le: string
  materiel: number
  materiel_nom: string
  materiel_code: string
  site_nom: string
  type: string
  type_libelle: string
  immobilisant: boolean
  description: string
  plan: number | null
  plan_intitule: string
  demandeur_nom: string
  mecanicien: number | null
  mecanicien_nom: string
  compteur_heures: string | null
  compteur_km: number | null
  diagnostic: string
  travaux: string
  demarre_le: string | null
  termine_le: string | null
  cloture_par_nom: string
  cloture_le: string | null
  motif_annulation: string
  pieces: { bon: number; bon_numero: string; date: string; code: string; designation: string; quantite: string; unite: string; prix_unitaire: string | null; montant: string | null }[]
  temps: { id: number; date: string; mecanicien: number; mecanicien_nom: string; heures: string; commentaire: string; montant: string | null; peut_retirer: boolean }[]
  couts: { heures: string; main_oeuvre: string; pieces: string; total: string; heures_non_chiffrees: string; pieces_sans_prix: number } | null
  peut_saisir_temps: boolean
  peut_travailler: boolean
  peut_piloter: boolean
}
export type Plan = {
  id: number
  materiel: number
  materiel_nom: string
  site_nom: string
  compteur_heures: string | null
  compteur_km: number | null
  intitule: string
  consignes: string
  intervalle_heures: string | null
  intervalle_km: number | null
  intervalle_mois: number | null
  dernier_le: string
  dernier_heures: string | null
  dernier_km: number | null
  actif: boolean
  situation: 'RETARD' | 'PROCHE' | 'A_VENIR'
  situation_libelle: string
  prochaine_date: string | null
  prochaines_heures: string | null
  prochain_km: number | null
  restes: { reste: string; unite: string }[]
  ordre_en_cours: { id: number; numero: string } | null
}
export const TYPES_MATERIEL = [
  ['CHARIOT', 'Chariot élévateur'], ['GRUE', 'Grue'], ['NACELLE', 'Nacelle'], ['CAMION', 'Camion'], ['TRACTEUR', 'Tracteur routier'],
  ['REMORQUE', 'Remorque ou semi-remorque'], ['VEHICULE', 'Véhicule léger'], ['GROUPE', 'Groupe électrogène ou compresseur'], ['AUTRE', 'Autre'],
]
export const ETATS_MATERIEL = [
  ['DISPONIBLE', 'Disponible'], ['EXPLOITE', 'En exploitation ou en location'], ['EN_PANNE', 'En panne'], ['REPARATION', 'En réparation'], ['REFORME', 'Réformé ou vendu'],
]
export const ACTIVITES = [['MANUTENTION', 'Manutention'], ['LEVAGE', 'Levage'], ['TRANSPORT', 'Transport'], ['AUTRE', 'Autre']]
export const TYPES_ORDRE = [['CORRECTIF', 'Panne (correctif)'], ['PREVENTIF', 'Entretien (préventif)'], ['ACCIDENT', 'Accident ou casse'], ['AMELIO', 'Modification ou amélioration']]
export const STATUTS_ORDRE = [['', 'Tous'], ['OUVERT', 'Ouverts'], ['EN_COURS', 'En cours'], ['TERMINE', 'Terminés, à clôturer'], ['CLOTURE', 'Clôturés'], ['ANNULE', 'Annulés']]
export const pastilleEtat = (e: string) => (e === 'DISPONIBLE' || e === 'EXPLOITE' ? 'complete' : e === 'REFORME' ? '' : 'u1')
