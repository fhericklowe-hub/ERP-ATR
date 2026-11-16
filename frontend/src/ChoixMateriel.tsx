import ChoixListe from './ChoixListe'

export type OptionMateriel = { id: number; code: string; designation: string; immatriculation?: string }

/** Choix d'un matériel : on cherche par numéro de parc, désignation ou immatriculation. */
export default function ChoixMateriel({ options, ...reste }: {
  options: OptionMateriel[]
  value: string
  onChange: (id: string) => void
  required?: boolean
  disabled?: boolean
  vide?: string
}) {
  return <ChoixListe {...reste} options={options.map((m) => ({ id: m.id, libelle: `${m.code} · ${m.designation}${m.immatriculation ? ` · ${m.immatriculation}` : ''}` }))} />
}
