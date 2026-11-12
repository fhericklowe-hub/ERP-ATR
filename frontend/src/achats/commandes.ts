import type { Evenement } from './types'

export type LigneCommande = {
  id?: number
  reference: string
  designation: string
  quantite: string
  prix_unitaire: string
  remise: string
  taux_tva: string
  prix_net?: string
  montant_ht?: string
  quantite_recue?: string
}

export type Totaux = {
  ventilation: { taux: string; base_ht: string; tva: string; ttc: string }[]
  total_ht: string
  total_tva: string
  total_ttc: string
  en_lettres: string
  devise: string
  contre_valeur_xof: string | null
}

export type Commande = {
  id: number
  numero: string
  ancien_numero: string
  statut: string
  statut_libelle: string
  date: string
  demande: number | null
  demande_budget: number | null
  demande_numero: string
  fournisseur: number | ''
  fournisseur_nom: string
  reference_fournisseur: string
  objet: string
  site: number | ''
  site_nom: string
  service: number | ''
  service_nom: string
  activite: string
  activite_autre: string
  activite_libelle: string
  acheteur_nom: string
  date_livraison: string | null
  transport: string
  adresse_livraison: string
  devise: string
  taux_change: string | null
  echeance: string
  mode_reglement: string
  mode_reglement_libelle: string
  transmis_le: string | null
  totaux: Totaux
  modifiable: boolean
  definitif: boolean
  peut_valider: boolean
  peut_preparer: boolean
  peut_annuler: boolean
  etat_reception: '' | 'AUCUNE' | 'PARTIELLE' | 'COMPLETE'
  etat_reception_libelle: string
  receptions: { id: number; numero: string; date: string; statut: string; statut_libelle: string; numero_livraison: string }[]
  lignes: LigneCommande[]
  evenements: Evenement[]
}

export const DEVISES = [['XOF', 'Franc CFA (XOF)'], ['EUR', 'Euro (EUR)'], ['USD', 'Dollar US (USD)']]
export const decimales = (devise = 'XOF') => (devise === 'XOF' ? 0 : 2)
/** Arrondi au franc, ou au centime en euro et en dollar. */
export const arrondi = (n: number, devise = 'XOF') => Number(n.toFixed(decimales(devise)))
export const montant = (n: string | number, devise = 'XOF') =>
  Number(n).toLocaleString('fr-FR', { minimumFractionDigits: decimales(devise), maximumFractionDigits: decimales(devise) })
