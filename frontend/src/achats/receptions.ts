export type LigneReception = {
  id?: number
  ligne_commande: number
  reference?: string
  designation?: string
  quantite_commandee?: string
  quantite_recue: string
  quantite_stock: string
  numero_materiel: string
  numero_serie: string
  immatriculation: string
  observations: string
  montant_ht?: string
}

export type Reception = {
  id: number
  numero: string
  ancien_numero: string
  statut: string
  statut_libelle: string
  date: string
  commande: number
  commande_numero: string
  fournisseur_nom: string
  site_nom: string
  service_nom: string
  objet: string
  devise: string
  numero_livraison: string
  receptionnaire_nom: string
  observations: string
  valide_le: string | null
  annule_par_nom: string
  annule_le: string | null
  motif_annulation: string
  total_ht: string
  modifiable: boolean
  peut_preparer: boolean
  peut_annuler: boolean
  lignes: LigneReception[]
}

export const qte = (n: string | number | undefined) => Number(n ?? 0).toLocaleString('fr-FR')
