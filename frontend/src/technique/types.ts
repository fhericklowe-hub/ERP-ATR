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
  pieces: { bon: number; bon_numero: string; date: string; code: string; designation: string; quantite: string; unite: string }[]
  peut_travailler: boolean
  peut_piloter: boolean
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
