import { type FormEvent, useRef, useState } from 'react'
import { api } from '../api'

type Bilan = { lues: number; crees: number; modifies: number; inchanges: number; erreurs: string[]; simulation: boolean; ecrit: boolean }

/** Parc de matériels depuis un classeur Excel. On contrôle d'abord, on importe ensuite. */
export default function ImportParc() {
  const [bilan, setBilan] = useState<Bilan | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const fichier = useRef<HTMLInputElement>(null)

  async function envoyer(simuler: boolean, e?: FormEvent) {
    e?.preventDefault()
    const f = fichier.current?.files?.[0]
    if (!f) return setErreur('Choisissez le fichier.')
    const corps = new FormData()
    corps.set('fichier', f)
    if (simuler) corps.set('simuler', '1')
    setErreur('')
    setEnCours(true)
    try {
      setBilan(await api<Bilan>('/technique/materiels/importer/', { method: 'POST', body: corps }))
    } catch (err) {
      setBilan(null)
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  const pret = bilan?.simulation && bilan.erreurs.length === 0 && bilan.lues > 0
  return (
    <form className="fiche" onSubmit={(e) => envoyer(true, e)}>
      <p><a href="#/parc">← Parc de matériels</a></p>
      <h2>Importer le parc depuis Excel</h2>
      <fieldset>
        <p className="aide">
          Première feuille du classeur, titres en première ligne : <strong>N° de parc, Désignation, Type, Site</strong>, puis au besoin
          Marque, Modèle, N° de série, Immatriculation, Année, Capacité, Activité, Compteur heures, Compteur km, Mise en service.
          Un n° de parc déjà connu est mis à jour (une case vide ne change rien), les autres matériels sont créés.
        </p>
        <p className="aide">Types reconnus : chariot élévateur, grue, nacelle, camion, tracteur routier, remorque, véhicule léger, groupe électrogène, autre.</p>
        <label>Classeur Excel (.xlsx)
          <input ref={fichier} type="file" accept=".xlsx" required onChange={() => setBilan(null)} />
        </label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {bilan && (
        <fieldset>
          <legend>{bilan.ecrit ? 'Import terminé' : bilan.erreurs.length ? 'Fichier à corriger : rien n\'a été importé' : 'Contrôle réussi'}</legend>
          <p role="status">
            {bilan.lues} ligne(s) lue(s) · {bilan.crees} matériel(s) {bilan.ecrit ? 'créé(s)' : 'à créer'} ·{' '}
            {bilan.modifies} {bilan.ecrit ? 'modifié(s)' : 'à modifier'} · {bilan.inchanges} inchangé(s)
          </p>
          {bilan.erreurs.length > 0 && <ul>{bilan.erreurs.map((x) => <li key={x} className="erreur">{x}</li>)}</ul>}
        </fieldset>
      )}
      <div className="actions">
        <button className={pret ? 'secondaire' : ''} disabled={enCours}>{enCours ? 'Lecture…' : 'Contrôler le fichier'}</button>
        {pret && <button type="button" disabled={enCours} onClick={() => envoyer(false)}>Importer</button>}
      </div>
    </form>
  )
}
