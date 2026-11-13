import { type FormEvent, useRef, useState } from 'react'
import { api } from '../api'

type Bilan = { lues: number; crees: number; modifies: number; inchanges: number; erreurs: string[]; simulation: boolean; ecrit: boolean }

/** Dossiers du personnel depuis un classeur Excel. On contrôle d'abord, on importe ensuite. */
export default function ImportPersonnel() {
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
      setBilan(await api<Bilan>('/rh/salaries/importer/', { method: 'POST', body: corps }))
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
      <p><a href="#/personnel">← Personnel</a></p>
      <h2>Importer le personnel depuis Excel</h2>
      <fieldset>
        <p className="aide">
          Première feuille du classeur, titres en première ligne : <strong>Nom, Prénoms, Site</strong>, puis au besoin Matricule, Sexe,
          Date de naissance, Lieu de naissance, Nationalité, Téléphone, E-mail, Adresse, N° CNPS, Service, Fonction, Catégorie,
          Date d'embauche, Solde de congés, Solde arrêté au.
        </p>
        <p className="aide">
          Un salarié déjà connu (même matricule, ou à défaut mêmes nom et prénoms) est mis à jour, et une case vide ne change rien.
          Les autres sont créés, avec un matricule automatique s'il n'est pas fourni. Catégories reconnues : cadre, agent de maîtrise, employé, ouvrier.
        </p>
        <label>Classeur Excel (.xlsx)
          <input ref={fichier} type="file" accept=".xlsx" required onChange={() => setBilan(null)} />
        </label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {bilan && (
        <fieldset>
          <legend>{bilan.ecrit ? 'Import terminé' : bilan.erreurs.length ? 'Fichier à corriger : rien n\'a été importé' : 'Contrôle réussi'}</legend>
          <p role="status">
            {bilan.lues} ligne(s) lue(s) · {bilan.crees} salarié(s) {bilan.ecrit ? 'créé(s)' : 'à créer'} ·{' '}
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
