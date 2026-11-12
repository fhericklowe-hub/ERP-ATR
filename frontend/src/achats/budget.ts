export type Devis = { id?: number; fournisseur: number | ''; fournisseur_nom?: string; numero: string; date: string | null; montant: string; retenu: boolean }

export type EvenementBudget = { id: number; action: string; action_libelle: string; etape_libelle: string; auteur_nom: string; date: string; commentaire: string }

export type SituationBudget = { budget: string; engage: string; disponible: string; a_engager: string; solde: string }

export type DemandeBudget = {
  id: number
  type: 'FG' | 'DI_NP' | 'DI_P'
  type_libelle: string
  numero: string
  ancien_numero: string
  statut: string
  statut_libelle: string
  date: string
  fast_track: boolean
  demandeur_nom: string
  demandeur_fonction: string
  service: number | ''
  service_nom: string
  site: number | ''
  site_nom: string
  activite: string
  activite_autre: string
  activite_libelle: string
  projet: number | null
  projet_nom: string
  code_analytique: string
  intitule: string
  description: string
  prevu_budget: boolean
  ligne_budgetaire: number | null
  ligne_budgetaire_nom: string
  motif_hors_budget: string
  nature: string
  nature_libelle: string
  motif_investissement: string
  motif_investissement_libelle: string
  numero_contrat: string
  client: number | null
  client_nom: string
  loyer_mensuel: string | null
  duree_amortissement: number | null
  acheteur_nom: string
  critere_qualite: boolean
  critere_delai: boolean
  critere_prix: boolean
  critere_autre: string
  justification_devis: string
  montant: string | null
  service_impute: number | null
  service_impute_nom: string
  compte: number | null
  compte_nom: string
  article_ng: string
  situation_budget: SituationBudget | null
  motifs_dg: string[]
  signatures: { etape: string; auteur: string; date: string | null }[]
  bons_commande: { id: number; numero: string; statut_libelle: string }[]
  est_investissement: boolean
  accord_dg_requis: boolean
  modifiable: boolean
  peut_valider: boolean
  peut_consulter: boolean
  peut_imputer: boolean
  peut_commander: boolean
  devis: Devis[]
  evenements: EvenementBudget[]
}

export type LigneBudgetaire = { id: number; exercice: number; service: number; service_nom: string; intitule: string; montant: string; disponible: string; actif: boolean }
export type Projet = { id: number; numero: number; nom: string; code_analytique: string; activite: string; type: string }
export type Compte = { id: number; numero: string; libelle: string; article_ng: string }

export const TYPES: [DemandeBudget['type'], string][] = [
  ['FG', 'Frais généraux et sous-traitance'],
  ['DI_NP', 'Investissement non productif'],
  ['DI_P', 'Investissement productif'],
]

export const NATURES: Record<string, [string, string][]> = {
  DI_NP: [
    ['CONSTRUCTIONS', 'Constructions'], ['INSTALL_TECH', 'Installations techniques'], ['MOB_BUREAU', 'Matériel et mobilier de bureau'],
    ['OUTILLAGE', 'Matériel et outillage'], ['INFORMATIQUE', 'Matériel informatique'], ['MOB_HABITAT', "Matériel et mobilier d'habitation"],
    ['TRANSPORT', 'Matériel de transport'], ['AGENCEMENTS', 'Agencements et installations'], ['AUTRES', 'Autres'],
  ],
  DI_P: [
    ['MANUTENTION', 'Matériel de manutention'], ['TRANSPORT', 'Matériel de transport'], ['LEVAGE', 'Matériel de levage et grutage'], ['AUTRES', 'Autres'],
  ],
}

export const STATUTS = [
  ['', 'Toutes'], ['BROUILLON', 'Brouillons'], ['ATT_SERVICE', 'Attente responsable de service'], ['ATT_ACCORD', 'Attente accord DG'],
  ['CONSULT', 'Consultation fournisseurs'], ['ATT_ACHATS', 'Attente responsable achats'], ['ATT_CDG', 'Attente contrôle de gestion'],
  ['ATT_RAF', 'Attente direction financière'], ['ATT_DG', 'Attente direction générale'], ['VALIDEE', 'Validées'], ['REFUSEE', 'Refusées'],
]
