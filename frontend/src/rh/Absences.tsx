import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateFr } from '../achats/types'
import { nombre } from '../stock/types'

type Absence = {
  id: number; numero: string; statut: string; statut_libelle: string; salarie: number; salarie_nom: string; matricule: string; site_nom: string
  type: string; type_libelle: string; date_debut: string; date_fin: string; jours: string; motif: string; vise_par_nom: string; vise_le: string | null
  approuve_par_nom: string; approuve_le: string | null; commentaire: string; peut_viser: boolean; peut_approuver: boolean; peut_annuler: boolean
}
export type Solde = { salarie: number | null; salarie_nom?: string; depuis?: string | null; repris?: string; acquis?: string; pris?: string; en_attente?: string; solde?: string }
type Personne = { id: number; nom_complet: string; matricule: string }

const TYPES = [['CONGE', 'Congé annuel'], ['PERMISSION', 'Permission exceptionnelle'], ['MALADIE', 'Maladie'], ['MATERNITE', 'Maternité ou paternité'],
  ['SANS_SOLDE', 'Absence sans solde'], ['AUTRE', 'Autre absence']]
const pastille = (a: Absence) => (a.statut === 'APPROUVEE' ? 'complete' : a.statut === 'REFUSEE' ? 'u1' : a.statut === 'ANNULEE' ? '' : 'partielle')
const jour = (d: Date) => d.toLocaleDateString('fr-CA')
const periode = (a: Absence) => (a.date_debut === a.date_fin ? `le ${dateFr(a.date_debut)}` : `du ${dateFr(a.date_debut)} au ${dateFr(a.date_fin)}`)

export function BlocSolde({ solde }: { solde: Solde }) {
  if (!solde.salarie) return <p className="aide">Votre compte n'est relié à aucun dossier de salarié : le solde de congés n'est pas disponible.</p>
  return (
    <p className="statut">Solde de congés : {nombre(solde.solde ?? '0')} jours
      <span className="aide"> · acquis {nombre(solde.acquis ?? '0')}{Number(solde.repris) ? ` + ${nombre(solde.repris ?? '0')} repris` : ''} · pris {nombre(solde.pris ?? '0')}{Number(solde.en_attente) ? ` · ${nombre(solde.en_attente ?? '0')} en attente d'accord` : ''}</span>
    </p>
  )
}

export function ListeAbsences({ voitTout }: { voitTout: boolean }) {
  const [liste, setListe] = useState<Absence[] | null>(null)
  const [aTraiter, setATraiter] = useState(0)
  const [solde, setSolde] = useState<Solde | null>(null)
  const [vue, setVue] = useState('miennes')
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Solde>('/rh/absences/solde/').then(setSolde).catch(() => undefined)
    api<Page<Absence>>('/rh/absences/?vue=a_traiter&page_size=1').then((p) => { setATraiter(p.count); if (p.count) setVue('a_traiter') }).catch(() => undefined)
  }, [])
  useEffect(() => {
    setListe(null)
    api<Page<Absence>>(`/rh/absences/?${vue === 'toutes' ? '' : `vue=${vue}&`}page_size=100`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [vue])
  const onglet = (v: string, texte: string) => <button type="button" className={vue === v ? '' : 'secondaire'} onClick={() => setVue(v)}>{texte}</button>
  return (
    <>
      <div className="barre">
        <h2>Congés et absences</h2>
        <div className="actions"><a className="bouton" href="#/absences/nouvelle">Nouvelle demande</a></div>
      </div>
      {solde && <BlocSolde solde={solde} />}
      <div className="actions">
        {onglet('miennes', 'Mes demandes')}{onglet('a_traiter', `À traiter${aTraiter ? ` (${aTraiter})` : ''}`)}{onglet('toutes', voitTout ? 'Toutes' : 'Mon équipe et moi')}
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucune demande.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Salarié</th><th>Absence</th><th>Période</th><th className="nombre">Jours</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((a) => (
                <tr key={a.id}>
                  <td><a href={`#/absences/${a.id}`}>{a.numero}</a></td><td>{a.salarie_nom}<br /><span className="aide">{a.site_nom}</span></td>
                  <td>{a.type_libelle}</td><td>{periode(a)}</td><td className="nombre">{nombre(a.jours)}</td>
                  <td><span className={`pastille ${pastille(a)}`}>{a.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireAbsence({ pourAutrui }: { pourAutrui: boolean }) {
  const [s, setS] = useState({ salarie: '', type: 'CONGE', date_debut: '', date_fin: '', motif: '' })
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [solde, setSolde] = useState<Solde | null>(null)
  const [jours, setJours] = useState<number | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    if (pourAutrui) api<Page<Personne>>('/rh/salaries/?statut=ACTIF&page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
  }, [pourAutrui])
  useEffect(() => {
    api<Solde>(`/rh/absences/solde/${s.salarie ? `?salarie=${s.salarie}` : ''}`).then(setSolde).catch(() => setSolde(null))
  }, [s.salarie])
  useEffect(() => {
    if (!s.date_debut || !s.date_fin) { setJours(null); return }
    api<{ jours: number }>(`/rh/absences/calcul/?debut=${s.date_debut}&fin=${s.date_fin}`).then((r) => setJours(r.jours)).catch(() => setJours(null))
  }, [s.date_debut, s.date_fin])

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const { salarie, ...corps } = s
      const r = await api<Absence>('/rh/absences/', { method: 'POST', body: JSON.stringify(salarie ? { ...corps, salarie: Number(salarie) } : corps) })
      location.hash = `#/absences/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  const trop = s.type === 'CONGE' && jours !== null && solde?.solde !== undefined && jours > Number(solde.solde)
  return (
    <form className="fiche" onSubmit={envoyer}>
      <p><a href="#/absences">← Congés et absences</a></p>
      <h2>Nouvelle demande d'absence</h2>
      {solde && (s.salarie || !pourAutrui || solde.salarie) && <BlocSolde solde={solde} />}
      <fieldset>
        <legend>Demande</legend>
        <div className="grille">
          {pourAutrui && (
            <label>Salarié
              <select value={s.salarie} onChange={(e) => setS({ ...s, salarie: e.target.value })}><option value="">Moi-même</option>{personnes.map((p) => <option key={p.id} value={p.id}>{p.nom_complet} ({p.matricule})</option>)}</select>
            </label>
          )}
          <label>Absence<select value={s.type} onChange={(e) => setS({ ...s, type: e.target.value })}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Du<input type="date" required value={s.date_debut} onChange={(e) => setS({ ...s, date_debut: e.target.value, date_fin: s.date_fin && s.date_fin >= e.target.value ? s.date_fin : e.target.value })} /></label>
          <label>Au (dernier jour d'absence)<input type="date" required min={s.date_debut} value={s.date_fin} onChange={(e) => setS({ ...s, date_fin: e.target.value })} /></label>
        </div>
        {jours !== null && <p className="aide">{jours} jour{jours > 1 ? 's' : ''} ouvrable{jours > 1 ? 's' : ''} (du lundi au samedi).{trop && ' Cette durée dépasse le solde de congés : les RH ne pourront pas l\'approuver telle quelle.'}</p>}
        <label>Motif{s.type === 'CONGE' ? ' (facultatif)' : ''}<input maxLength={200} required={s.type !== 'CONGE'} placeholder={s.type === 'PERMISSION' ? 'Mariage, naissance, décès…' : ''} value={s.motif} onChange={(e) => setS({ ...s, motif: e.target.value })} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions"><button disabled={enCours}>Envoyer la demande</button></div>
    </form>
  )
}

export function DetailAbsence({ id }: { id: number }) {
  const [a, setA] = useState<Absence | null>(null)
  const [solde, setSolde] = useState<Solde | null>(null)
  const [commentaire, setCommentaire] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const recevoir = useCallback((x: Absence) => {
    setA(x)
    setCommentaire('')
    if (x.type === 'CONGE') api<Solde>(`/rh/absences/solde/?salarie=${x.salarie}`).then(setSolde).catch(() => setSolde(null))
  }, [])
  useEffect(() => {
    api<Absence>(`/rh/absences/${id}/`).then(recevoir).catch((e: Error) => setErreur(e.message))
  }, [id, recevoir])

  async function agir(action: string, corps: object = {}) {
    setErreur('')
    setEnCours(true)
    try {
      recevoir(await api<Absence>(`/rh/absences/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  if (!a) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const decide = a.peut_viser || a.peut_approuver
  return (
    <div className="fiche">
      <p><a href="#/absences">← Congés et absences</a></p>
      <div className="barre"><h2>Demande {a.numero}</h2></div>
      <p className="statut">{a.statut_libelle}</p>
      <dl>
        <dt>Salarié</dt><dd><strong>{a.salarie_nom}</strong> · {a.matricule} · {a.site_nom}</dd>
        <dt>Absence</dt><dd>{a.type_libelle}</dd>
        <dt>Période</dt><dd>{periode(a)} · {nombre(a.jours)} jour{Number(a.jours) > 1 ? 's' : ''} ouvrable{Number(a.jours) > 1 ? 's' : ''}</dd>
        {a.motif && <><dt>Motif</dt><dd>{a.motif}</dd></>}
        {a.vise_le && <><dt>Responsable</dt><dd>accord de {a.vise_par_nom} le {dateFr(a.vise_le)}</dd></>}
        {a.approuve_le && <><dt>RH</dt><dd>approuvée par {a.approuve_par_nom} le {dateFr(a.approuve_le)}</dd></>}
        {a.commentaire && <><dt>{a.statut === 'REFUSEE' ? 'Refus' : 'Annulation'}</dt><dd>{a.commentaire}</dd></>}
      </dl>
      {solde && decide && <BlocSolde solde={solde} />}
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {(decide || a.peut_annuler) && (
        <fieldset>
          <legend>{decide ? 'Décision' : 'Annulation'}</legend>
          <label>Motif (pour un refus ou une annulation)<textarea value={commentaire} onChange={(e) => setCommentaire(e.target.value)} /></label>
          <div className="actions">
            {a.peut_viser && <button disabled={enCours} onClick={() => agir('viser')}>Donner mon accord</button>}
            {a.peut_approuver && <button disabled={enCours} onClick={() => agir('approuver')}>Approuver</button>}
            {decide && <button className="secondaire" disabled={enCours} onClick={() => agir('refuser', { commentaire })}>Refuser</button>}
            {a.peut_annuler && <button className="danger" disabled={enCours} onClick={() => agir('annuler', { commentaire })}>Annuler la demande</button>}
          </div>
        </fieldset>
      )}
    </div>
  )
}

export function PlanningAbsences() {
  const [liste, setListe] = useState<Absence[] | null>(null)
  const [p, setP] = useState(() => { const fin = new Date(); fin.setDate(fin.getDate() + 30); return { debut: jour(new Date()), fin: jour(fin) } })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    if (p.debut && p.fin) api<Absence[]>(`/rh/absences/planning/?${new URLSearchParams(p)}`).then(setListe).catch((e: Error) => setErreur(e.message))
  }, [p])
  return (
    <>
      <div className="barre"><h2>Planning des absences</h2></div>
      <p className="aide">Qui est absent sur la période : absences approuvées et demandes en attente.</p>
      <div className="grille filtres">
        <label>Du<input type="date" value={p.debut} onChange={(e) => setP({ ...p, debut: e.target.value })} /></label>
        <label>Au<input type="date" min={p.debut} value={p.fin} onChange={(e) => setP({ ...p, fin: e.target.value })} /></label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {liste?.length === 0 && <p className="aide">Aucune absence sur cette période.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Salarié</th><th>Absence</th><th>Période</th><th className="nombre">Jours</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((a) => (
                <tr key={a.id}>
                  <td>{a.salarie_nom}<br /><span className="aide">{a.site_nom}</span></td><td><a href={`#/absences/${a.id}`}>{a.type_libelle}</a></td>
                  <td>{periode(a)}</td><td className="nombre">{nombre(a.jours)}</td><td><span className={`pastille ${pastille(a)}`}>{a.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
