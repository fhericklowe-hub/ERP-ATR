export type Bien = {
  id: number
  numero: string
  categorie: string
  categorie_libelle: string
  designation: string
  marque: string
  modele: string
  numero_serie: string
  immatriculation: string
  site: number | ''
  site_nom: string
  emplacement: string
  service: number | null
  service_nom: string
  affecte_a: number | null
  affecte_a_nom: string
  date_acquisition: string | null
  valeur_acquisition: string | null
  etat: string
  etat_libelle: string
  observations: string
  interventions_ouvertes: number
}

export type Intervention = {
  id: number
  numero: string
  statut: string
  statut_libelle: string
  cree_le: string
  demandeur_nom: string
  service: number | ''
  service_nom: string
  site: number | ''
  site_nom: string
  lieu: string
  bien: number | null
  bien_nom: string
  categorie: string
  categorie_libelle: string
  priorite: number
  priorite_libelle: string
  objet: string
  description: string
  intervenant: number | null
  intervenant_nom: string
  prestataire: number | null
  prestataire_nom: string
  date_prevue: string | null
  realisee_le: string | null
  compte_rendu: string
  cout: string | null
  modifiable: boolean
  peut_traiter: boolean
  peut_realiser: boolean
  peut_cloturer: boolean
  evenements: { id: number; action_libelle: string; auteur_nom: string; date: string; commentaire: string }[]
}

export const CATEGORIES_BIEN = [
  ['BATIMENT', 'Bâtiment ou local'], ['VEHICULE', 'Véhicule de service'], ['MOBILIER', 'Mobilier'], ['INFORMATIQUE', 'Matériel informatique'],
  ['TELEPHONIE', 'Téléphonie'], ['EQUIPEMENT', 'Équipement (climatisation, groupe électrogène...)'], ['AUTRE', 'Autre'],
]
export const ETATS_BIEN = [['EN_SERVICE', 'En service'], ['EN_PANNE', 'En panne'], ['REPARATION', 'En réparation'], ['REFORME', 'Réformé']]
export const CATEGORIES = [
  ['ELECTRICITE', 'Électricité'], ['PLOMBERIE', 'Plomberie'], ['CLIMATISATION', 'Climatisation'],
  ['BATIMENT', 'Bâtiment (menuiserie, serrurerie, peinture)'], ['INFORMATIQUE', 'Informatique et téléphonie'],
  ['VEHICULE', 'Véhicule de service'], ['MOBILIER', 'Mobilier'], ['NETTOYAGE', 'Nettoyage et entretien'], ['AUTRE', 'Autre'],
]
export const STATUTS = [
  ['', 'Toutes'], ['NOUVELLE', 'Nouvelles'], ['EN_COURS', 'Prises en charge'], ['REALISEE', 'Réalisées, à confirmer'],
  ['CLOTUREE', 'Clôturées'], ['REFUSEE', 'Refusées'],
]

export type Contrat = {
  id: number
  numero: string
  type: string
  type_libelle: string
  objet: string
  prestataire: number | ''
  prestataire_nom: string
  reference: string
  site: number | null
  site_nom: string
  bien: number | null
  bien_nom: string
  date_debut: string
  date_fin: string | null
  tacite_reconduction: boolean
  preavis_jours: number
  date_limite_preavis: string | null
  montant: string | null
  periodicite: string
  periodicite_libelle: string
  statut: string
  statut_libelle: string
  observations: string
}

export type Echeance = {
  id: number
  type: string
  type_libelle: string
  libelle: string
  date_echeance: string
  rappel_jours: number
  recurrence_mois: number
  site: number | null
  site_nom: string
  bien: number | null
  bien_nom: string
  contrat: number | null
  contrat_numero: string
  montant_prevu: string | null
  statut: string
  statut_libelle: string
  situation: 'RETARD' | 'PROCHE' | 'A_VENIR' | 'FAITE' | 'ANNULEE'
  jours_restants: number
  faite_le: string | null
  montant_reel: string | null
  commentaire: string
}

export const TYPES_CONTRAT = [
  ['ASSURANCE', 'Assurance'], ['BAIL', 'Bail ou location'], ['MAINTENANCE', 'Maintenance et entretien'],
  ['GARDIENNAGE', 'Gardiennage et sécurité'], ['NETTOYAGE', 'Nettoyage'],
  ['ABONNEMENT', 'Abonnement (eau, électricité, téléphone, internet)'], ['AUTRE', 'Autre'],
]
export const PERIODICITES = [['M', 'Par mois'], ['T', 'Par trimestre'], ['S', 'Par semestre'], ['A', 'Par an'], ['U', 'En une fois']]
export const TYPES_ECHEANCE = [
  ['ASSURANCE', 'Assurance'], ['VISITE', 'Visite technique'], ['VIGNETTE', 'Vignette, patente et taxes'],
  ['CONTROLE', 'Contrôle réglementaire (extincteurs, électricité...)'], ['PAIEMENT', 'Loyer ou paiement'], ['AUTRE', 'Autre'],
]
export const RECURRENCES = [[0, 'Ne revient pas'], [1, 'Tous les mois'], [3, 'Tous les 3 mois'], [6, 'Tous les 6 mois'], [12, 'Tous les ans'], [24, 'Tous les 2 ans']] as const
