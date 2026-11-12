export type LigneStock = {
  article: number
  code: string
  designation: string
  unite: string
  magasin: number
  magasin_nom: string
  quantite: string
  seuil_mini: string
  casier: string
  reglage: number | null
  alerte: boolean
}
export type EtatStock = { count: number; results: LigneStock[]; peut_ajuster: boolean; peut_sortir: boolean }
export type Mouvement = {
  id: number; date: string; type: string; type_libelle: string; article_nom: string; magasin_nom: string
  quantite: string; motif: string; auteur_nom: string
}
export type Magasin = { id: number; nom: string }
export type Sortie = {
  id: number
  numero: string
  statut: string
  statut_libelle: string
  date: string
  magasin: number
  magasin_nom: string
  numero_or: string
  materiel: string
  remis_a_nom: string
  service_nom: string
  observations: string
  magasinier_nom: string
  annule_par_nom: string
  annule_le: string | null
  motif_annulation: string
  peut_annuler: boolean
  lignes: { id: number; article: number; code: string; designation: string; unite: string; quantite: string }[]
}
export const nombre = (q: string | number) => Number(q).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
