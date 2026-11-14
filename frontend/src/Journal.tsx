import { useEffect, useState } from 'react'
import { api, type Page } from './api'
import BoutonExcel from './BoutonExcel'
import { dateHeureFr } from './achats/types'

type Detail = { champ: string; avant: unknown; apres: unknown; masque: boolean }
type Trace = {
  id: number; date: string; utilisateur_nom: string; action: string; action_libelle: string
  modele_libelle: string; objet_libelle: string; details: Detail[]
}
type Personne = { id: number; username: string; first_name: string; last_name: string }

const TAILLE = 50
const texte = (v: unknown) => (v === null || v === undefined || v === '' ? '(vide)' : v === true ? 'oui' : v === false ? 'non' : String(v))

/** Qui a créé, modifié ou supprimé quoi, et quand. Lecture seule. */
export default function Journal() {
  const [filtre, setFiltre] = useState({ search: '', action: '', utilisateur: '', date__gte: '', date__lte: '' })
  const [page, setPage] = useState(1)
  const [liste, setListe] = useState<Trace[] | null>(null)
  const [total, setTotal] = useState(0)
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [erreur, setErreur] = useState('')

  const requete = (f: typeof filtre) => ({ ...f, date__lte: f.date__lte ? `${f.date__lte}T23:59:59` : '' })
  useEffect(() => {
    api<Page<Personne>>('/utilisateurs/?page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
  }, [])
  useEffect(() => {
    const q = new URLSearchParams({ page: String(page), page_size: String(TAILLE) })
    Object.entries(requete(filtre)).forEach(([k, v]) => { if (v) q.set(k, v) })
    const t = setTimeout(() => {
      api<Page<Trace>>(`/journal/?${q}`).then((p) => { setListe(p.results); setTotal(p.count); setErreur('') }).catch((e: Error) => setErreur(e.message))
    }, 200)
    return () => clearTimeout(t)
  }, [filtre, page])

  const change = (k: keyof typeof filtre, v: string) => { setPage(1); setFiltre({ ...filtre, [k]: v }) }
  const pages = Math.max(1, Math.ceil(total / TAILLE))

  return (
    <>
      <div className="barre">
        <h2>Journal des modifications</h2>
        <div className="actions"><BoutonExcel chemin="/journal/" nom="journal" filtres={requete(filtre)} onErreur={setErreur} /></div>
      </div>
      <p className="aide">Toute création, modification ou suppression faite dans l'application. Les valeurs des dossiers du personnel et des mots de passe ne sont jamais écrites.</p>
      <div className="grille filtres large">
        <label>Recherche<input value={filtre.search} placeholder="Numéro, nom, code…" onChange={(e) => change('search', e.target.value)} /></label>
        <label>Action
          <select value={filtre.action} onChange={(e) => change('action', e.target.value)}>
            <option value="">Toutes</option><option value="CREATION">Créations</option><option value="MODIFICATION">Modifications</option><option value="SUPPRESSION">Suppressions</option>
          </select>
        </label>
        <label>Utilisateur
          <select value={filtre.utilisateur} onChange={(e) => change('utilisateur', e.target.value)}>
            <option value="">Tous</option>
            {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
          </select>
        </label>
        <label>Du<input type="date" value={filtre.date__gte} onChange={(e) => change('date__gte', e.target.value)} /></label>
        <label>Au<input type="date" value={filtre.date__lte} onChange={(e) => change('date__lte', e.target.value)} /></label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p>Aucune entrée.</p>}
      {liste && liste.length > 0 && (
        <>
          <div className="defilant">
            <table>
              <thead><tr><th>Date</th><th>Utilisateur</th><th>Action</th><th>Objet</th><th>Détail</th></tr></thead>
              <tbody>
                {liste.map((t) => (
                  <tr key={t.id}>
                    <td>{dateHeureFr(t.date)}</td>
                    <td>{t.utilisateur_nom}</td>
                    <td><span className={`pastille ${t.action === 'SUPPRESSION' ? 'panne' : ''}`}>{t.action_libelle}</span></td>
                    <td>{t.modele_libelle}<br /><span className="aide">{t.objet_libelle}</span></td>
                    <td>
                      {t.details.length === 0 ? <span className="aide">—</span> : (
                        <details>
                          <summary>{t.details.map((d) => d.champ).join(', ')}</summary>
                          <ul>
                            {t.details.map((d) => (
                              <li key={d.champ}>{d.masque ? <>{d.champ} : <em>modifié (valeur non conservée)</em></> : <>{d.champ} : {texte(d.avant)} → <strong>{texte(d.apres)}</strong></>}</li>
                            ))}
                          </ul>
                        </details>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="actions">
            <button className="secondaire" disabled={page <= 1} onClick={() => setPage(page - 1)}>Plus récentes</button>
            <span className="aide">Page {page} sur {pages} · {total} entrées</span>
            <button className="secondaire" disabled={page >= pages} onClick={() => setPage(page + 1)}>Plus anciennes</button>
          </div>
        </>
      )}
    </>
  )
}
