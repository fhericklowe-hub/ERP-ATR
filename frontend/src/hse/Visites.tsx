import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site } from '../api'
import PiecesJointes from '../PiecesJointes'
import { dateFr } from '../achats/types'
import ActionsCorrectives, { type Action } from './Actions'

type Visite = {
  id: number; numero: string; statut: string; statut_libelle: string; date: string; site: number | ''; site_nom: string; lieu: string; participants: string
  visiteur_nom: string; points_positifs: string; ecarts: string; clos_le: string | null; actions: Action[]; actions_a_faire: number
  peut_modifier: boolean; peut_clore: boolean
}
const aujourdHui = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10)
const pastille = (v: Visite) => (v.statut === 'CLOSE' ? 'complete' : v.actions_a_faire ? 'partielle' : '')

export function ListeVisites({ peutCreer }: { peutCreer: boolean }) {
  const [liste, setListe] = useState<Visite[] | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [filtre, setFiltre] = useState({ search: '', statut: '', site: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => { api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined) }, [])
  useEffect(() => {
    api<Page<Visite>>(`/hse/visites/?${new URLSearchParams(filtre)}&page_size=100`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Visites de sécurité</h2>
        {peutCreer && <div className="actions"><a className="bouton" href="#/hse/visites/nouvelle">Enregistrer une visite</a></div>}
      </div>
      <div className="grille filtres large">
        <label>Recherche<input placeholder="N°, lieu, constat" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Site<select value={filtre.site} onChange={(e) => setFiltre({ ...filtre, site: e.target.value })}><option value="">Tous</option>{sites.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
        <label>État<select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}><option value="">Toutes</option><option value="OUVERTE">Non closes</option><option value="CLOSE">Closes</option></select></label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucune visite de sécurité.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Date</th><th>Lieu</th><th>Menée par</th><th>Actions</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((v) => (
                <tr key={v.id}>
                  <td><a href={`#/hse/visites/${v.id}`}>{v.numero}</a></td><td>{dateFr(v.date)}</td><td>{[v.site_nom, v.lieu].filter(Boolean).join(' · ')}</td>
                  <td>{v.visiteur_nom}</td><td>{v.actions.length ? `${v.actions.length - v.actions_a_faire} / ${v.actions.length}` : ''}</td>
                  <td><span className={`pastille ${pastille(v)}`}>{v.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireVisite({ id }: { id?: number }) {
  const [s, setS] = useState({ date: aujourdHui(), site: '' as number | '', lieu: '', participants: '', points_positifs: '', ecarts: '' })
  const [sites, setSites] = useState<Site[]>([])
  const [pret, setPret] = useState(!id)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    if (id) api<Visite>(`/hse/visites/${id}/`).then((v) => {
      setS({ date: v.date, site: v.site, lieu: v.lieu, participants: v.participants, points_positifs: v.points_positifs, ecarts: v.ecarts })
      setPret(true)
    }).catch((e: Error) => setErreur(e.message))
  }, [id])

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const r = await api<Visite>(id ? `/hse/visites/${id}/` : '/hse/visites/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(s) })
      location.hash = `#/hse/visites/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  if (!pret) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  return (
    <form className="fiche" onSubmit={envoyer}>
      <p><a href={id ? `#/hse/visites/${id}` : '#/hse/visites'}>← Retour</a></p>
      <h2>{id ? 'Corriger la visite' : 'Enregistrer une visite de sécurité'}</h2>
      <fieldset>
        <legend>Visite</legend>
        <div className="grille">
          <label>Date<input type="date" required max={aujourdHui()} value={s.date} onChange={(e) => setS({ ...s, date: e.target.value })} /></label>
          <label>Site<select required value={s.site} onChange={(e) => setS({ ...s, site: Number(e.target.value) || '' })}><option value="">Choisir</option>{sites.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
          <label>Lieu ou activité visités<input required maxLength={200} placeholder="Atelier, parc, chantier du client, opération de levage…" value={s.lieu} onChange={(e) => setS({ ...s, lieu: e.target.value })} /></label>
          <label>Participants<input maxLength={300} placeholder="Personnes rencontrées ou accompagnant la visite" value={s.participants} onChange={(e) => setS({ ...s, participants: e.target.value })} /></label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Constats</legend>
        <label>Bonnes pratiques constatées<textarea rows={3} value={s.points_positifs} onChange={(e) => setS({ ...s, points_positifs: e.target.value })} /></label>
        <label>Écarts constatés<textarea rows={4} placeholder="Un écart par ligne" value={s.ecarts} onChange={(e) => setS({ ...s, ecarts: e.target.value })} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions"><button disabled={enCours}>{id ? 'Enregistrer' : 'Enregistrer la visite'}</button></div>
      {!id && <p className="aide">Vous déciderez des actions correctives et joindrez des photos une fois la visite enregistrée.</p>}
    </form>
  )
}

export function DetailVisite({ id }: { id: number }) {
  const [v, setV] = useState<Visite | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => {
    api<Visite>(`/hse/visites/${id}/`).then(setV).catch((err: Error) => setErreur(err.message))
  }, [id])
  useEffect(charger, [charger])

  async function passer(transition: string) {
    setErreur('')
    setEnCours(true)
    try {
      setV(await api<Visite>(`/hse/visites/${id}/${transition}/`, { method: 'POST', body: '{}' }))
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  if (!v) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const ouverte = v.statut === 'OUVERTE'
  return (
    <div className="fiche">
      <p><a href="#/hse/visites">← Visites de sécurité</a></p>
      <div className="barre">
        <h2>Visite de sécurité {v.numero}</h2>
        {v.peut_modifier && <div className="actions"><a className="bouton secondaire" href={`#/hse/visites/${id}/modifier`}>Corriger</a></div>}
      </div>
      <p className="statut">{v.statut_libelle}</p>
      <dl>
        <dt>Date</dt><dd>{dateFr(v.date)}</dd>
        <dt>Lieu</dt><dd>{[v.site_nom, v.lieu].filter(Boolean).join(' · ')}</dd>
        <dt>Menée par</dt><dd>{v.visiteur_nom}</dd>
        {v.participants && <><dt>Participants</dt><dd>{v.participants}</dd></>}
        {v.points_positifs && <><dt>Bonnes pratiques</dt><dd style={{ whiteSpace: 'pre-line' }}>{v.points_positifs}</dd></>}
        {v.ecarts && <><dt>Écarts</dt><dd style={{ whiteSpace: 'pre-line' }}>{v.ecarts}</dd></>}
        {v.clos_le && <><dt>Close</dt><dd>le {dateFr(v.clos_le)}</dd></>}
      </dl>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <ActionsCorrectives actions={v.actions} origine={{ visite: id }} peutAjouter={v.peut_modifier} peutAbandonner={v.peut_clore} recharger={charger} />
      {v.peut_clore && ouverte && (
        <div className="actions">
          <button disabled={enCours || v.actions_a_faire > 0} onClick={() => passer('clore')}>Clore la visite</button>
          {v.actions_a_faire > 0 && <span className="aide">La visite se clôt quand toutes les actions sont faites ou abandonnées.</span>}
        </div>
      )}
      {v.peut_clore && !ouverte && <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => passer('rouvrir')}>Rouvrir</button></div>}
      <PiecesJointes modele="hse.visite" objet={id} aide="Joignez ici les photos prises pendant la visite." />
    </div>
  )
}
