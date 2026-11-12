import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { api, ouvrirFichier } from './api'

type Piece = { id: number; nom: string; libelle: string; taille: number; ajoute_par_nom: string; ajoute_le: string; supprimable: boolean }

const taille = (o: number) => (o < 1024 * 1024 ? `${Math.max(1, Math.round(o / 1024))} Ko` : `${(o / 1024 / 1024).toFixed(1).replace('.', ',')} Mo`)

/** Pièces jointes d'un document (devis, facture, contrat signé, photo). Les droits sont ceux du document. */
export default function PiecesJointes({ modele, objet, aide }: { modele: string; objet: number; aide?: string }) {
  const [pieces, setPieces] = useState<Piece[]>([])
  const [peutAjouter, setPeutAjouter] = useState(false)
  const [libelle, setLibelle] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const fichier = useRef<HTMLInputElement>(null)

  const charger = useCallback(() => {
    api<{ peut_ajouter: boolean; results: Piece[] }>(`/pieces-jointes/?modele=${modele}&objet=${objet}`)
      .then((r) => { setPieces(r.results); setPeutAjouter(r.peut_ajouter) })
      .catch(() => undefined)
  }, [modele, objet])
  useEffect(charger, [charger])

  async function joindre(e: FormEvent) {
    e.preventDefault()
    const f = fichier.current?.files?.[0]
    if (!f) return setErreur('Choisissez un fichier.')
    const corps = new FormData()
    corps.set('modele', modele)
    corps.set('objet', String(objet))
    corps.set('libelle', libelle)
    corps.set('fichier', f)
    setEnCours(true)
    setErreur('')
    try {
      await api('/pieces-jointes/', { method: 'POST', body: corps })
      setLibelle('')
      if (fichier.current) fichier.current.value = ''
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  async function retirer(p: Piece) {
    if (!confirm(`Retirer « ${p.libelle || p.nom} » ?`)) return
    setErreur('')
    try {
      await api(`/pieces-jointes/${p.id}/`, { method: 'DELETE' })
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  if (!peutAjouter && pieces.length === 0) return null

  return (
    <fieldset className="pieces">
      <legend>Pièces jointes</legend>
      {pieces.length === 0 && <p className="aide">{aide ?? 'Aucune pièce jointe.'}</p>}
      {pieces.length > 0 && (
        <ul>
          {pieces.map((p) => (
            <li key={p.id}>
              <button type="button" className="lien" onClick={() => ouvrirFichier(`/pieces-jointes/${p.id}/telecharger/`).catch((e: Error) => setErreur(e.message))}>
                {p.libelle || p.nom}
              </button>
              <span className="aide"> {p.libelle && `${p.nom} · `}{taille(p.taille)} · {p.ajoute_par_nom}, le {new Date(p.ajoute_le).toLocaleDateString('fr-FR')}</span>
              {p.supprimable && <> <button type="button" className="discret" onClick={() => retirer(p)}>Retirer</button></>}
            </li>
          ))}
        </ul>
      )}
      {peutAjouter && (
        <form className="grille" onSubmit={joindre}>
          <label>Fichier (PDF, image, Word, Excel ; 10 Mo au plus)
            <input ref={fichier} type="file" accept=".pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx,.csv,.txt,.msg,.eml" />
          </label>
          <label>Libellé (facultatif)
            <input value={libelle} maxLength={120} placeholder="Exemple : devis du fournisseur retenu" onChange={(e) => setLibelle(e.target.value)} />
          </label>
          <div className="actions"><button className="secondaire" disabled={enCours}>{enCours ? 'Envoi…' : 'Joindre'}</button></div>
        </form>
      )}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
    </fieldset>
  )
}
