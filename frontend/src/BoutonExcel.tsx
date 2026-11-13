import { useState } from 'react'
import { telechargerFichier } from './api'

/** Télécharge en Excel la liste affichée, avec les mêmes filtres que l'écran. */
export default function BoutonExcel({ chemin, filtres, nom, onErreur }: {
  chemin: string
  filtres?: Record<string, string>
  nom: string
  onErreur: (message: string) => void
}) {
  const [enCours, setEnCours] = useState(false)
  async function exporter() {
    setEnCours(true)
    onErreur('')
    const q = new URLSearchParams(Object.entries(filtres ?? {}).filter(([, v]) => v !== ''))
    try {
      await telechargerFichier(`${chemin}exporter/?${q}`, `${nom}-${new Date().toISOString().slice(0, 10)}.xlsx`)
    } catch (e) {
      onErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  return <button type="button" className="secondaire" disabled={enCours} onClick={exporter}>{enCours ? 'Export…' : 'Exporter vers Excel'}</button>
}
