export type Ligne = {
  id?: number
  designation: string
  reference_constructeur: string
  quantite: string
  unite: number | ''
  unite_code?: string
  observations: string
}

export type Evenement = {
  id: number
  action_libelle: string
  auteur_nom: string
  date: string
  commentaire: string
}

export type Demande = {
  id: number
  numero: string
  ancien_numero: string
  statut: string
  statut_libelle: string
  date_demande: string
  demandeur: number
  demandeur_nom: string
  service: number | ''
  service_nom: string
  site: number | ''
  site_nom: string
  telephone: string
  numero_or: string
  date_besoin: string | null
  piece_technique: boolean
  equipement_designation: string
  equipement_marque: string
  equipement_modele: string
  equipement_serie: string
  activite: string
  activite_autre: string
  urgence: number
  justification_urgence: string
  recue_le: string | null
  echeance_commande: string | null
  en_retard: boolean
  elements_manquants: string
  controle_stock: string
  modifiable: boolean
  peut_valider: boolean
  lignes: Ligne[]
  pieces_jointes: { id: number; fichier: string }[]
  evenements: Evenement[]
}

export const URGENCES: Record<number, string> = { 1: 'Urgent', 2: 'Normal', 3: 'Planifié' }

export const dateFr = (d: string | null) => (d ? new Date(d).toLocaleDateString('fr-FR') : '')
export const dateHeureFr = (d: string | null) =>
  d ? new Date(d).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : ''
