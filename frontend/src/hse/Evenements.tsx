import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site } from '../api'
import PiecesJointes from '../PiecesJointes'
import { dateFr } from '../achats/types'

type Action = {
  id: number; evenement: number; evenement_numero: string; statut: string; statut_libelle: string; description: string; responsable: number
  responsable_nom: string; echeance: string; faite_le: string | null; commentaire: string; en_retard: boolean; peut_agir: boolean
}
type Evenement = {
  id: number; numero: string; statut: string; statut_libelle: string; type: string; type_libelle: string; gravite: string; gravite_libelle: string
  date: string; site: number | ''; site_nom: string; lieu: string; description: string; personnes: string; materiel: number | null; materiel_nom: string
  mesures_immediates: string; jours_arret: number; declarant_nom: string; causes: string; conclusion: string; clos_le: string | null; clos_par_nom: string
  actions: Action[]; actions_a_faire: number; peut_traiter: boolean; peut_modifier: boolean
}
type Indicateurs = { annee: number; total: number; par_type: { type: string; libelle: string; nombre: number }[]; accidents_avec_arret: number; jours_arret: number; jours_sans_accident: number | null; a_traiter: number; actions_en_retard: number }
type Materiel = { id: number; code: string; designation: string }
type Compte = { id: number; username: string; first_name: string; last_name: string }

const TYPES = [['PRESQUE', "Presqu'accident"], ['DANGER', 'Situation dangereuse'], ['ACCIDENT', 'Accident du travail'], ['SOIN', 'Premiers soins'],
  ['MATERIEL', 'Dégât matériel'], ['ENVIRON', "Atteinte à l'environnement"]]
const GRAVITES = [['1', 'Mineure'], ['2', 'Sérieuse'], ['3', 'Grave']]
const STATUTS = [['', 'Tous'], ['DECLARE', 'Déclarés'], ['ANALYSE', 'En cours de traitement'], ['CLOS', 'Clos']]
const pastille = (e: Evenement) => (e.statut === 'CLOS' ? 'complete' : e.statut === 'DECLARE' ? 'u1' : 'partielle')
const pastilleGravite = (g: string) => (g === '3' ? 'u1' : g === '2' ? 'partielle' : '')
const maintenant = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)
const moment = (d: string) => new Date(d).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })

export function ListeEvenements({ peutTraiter }: { peutTraiter: boolean }) {
  const [liste, setListe] = useState<Evenement[] | null>(null)
  const [chiffres, setChiffres] = useState<Indicateurs | null>(null)
  const [miennes, setMiennes] = useState<Action[]>([])
  const [filtre, setFiltre] = useState({ search: '', statut: '', type: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    if (peutTraiter) api<Indicateurs>('/hse/evenements/indicateurs/').then(setChiffres).catch(() => undefined)
    api<Page<Action>>('/hse/actions/?miennes=1&statut=A_FAIRE&page_size=50').then((p) => setMiennes(p.results)).catch(() => undefined)
  }, [peutTraiter])
  useEffect(() => {
    api<Page<Evenement>>(`/hse/evenements/?${new URLSearchParams(filtre)}&page_size=100`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Événements HSE</h2>
        <div className="actions"><a className="bouton" href="#/hse/nouveau">Déclarer un événement</a></div>
      </div>
      {chiffres && (
        <>
          <p className="statut">{chiffres.jours_sans_accident === null ? 'Aucun accident avec arrêt enregistré' : `${chiffres.jours_sans_accident} jour${chiffres.jours_sans_accident > 1 ? 's' : ''} sans accident avec arrêt`}</p>
          <p className="aide">En {chiffres.annee} : {chiffres.total} événement{chiffres.total > 1 ? 's' : ''} ({chiffres.par_type.filter((t) => t.nombre).map((t) => `${t.libelle.toLowerCase()} : ${t.nombre}`).join(', ') || 'aucun'}) · {chiffres.accidents_avec_arret} accident{chiffres.accidents_avec_arret > 1 ? 's' : ''} avec arrêt, {chiffres.jours_arret} jour{chiffres.jours_arret > 1 ? 's' : ''} d'arrêt · {chiffres.a_traiter} à traiter · {chiffres.actions_en_retard} action{chiffres.actions_en_retard > 1 ? 's' : ''} en retard</p>
        </>
      )}
      {miennes.length > 0 && (
        <fieldset>
          <legend>Mes actions à faire</legend>
          <ul>{miennes.map((a) => <li key={a.id}><a href={`#/hse/${a.evenement}`}>{a.evenement_numero}</a> · {a.description} · avant le {dateFr(a.echeance)} {a.en_retard && <span className="pastille u1">en retard</span>}</li>)}</ul>
        </fieldset>
      )}
      <div className="grille filtres large">
        <label>Recherche<input placeholder="N°, description, lieu" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Type<select value={filtre.type} onChange={(e) => setFiltre({ ...filtre, type: e.target.value })}><option value="">Tous</option>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label>État<select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>{STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun événement.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Date</th><th>Type</th><th>Lieu</th><th>Gravité</th><th>Actions</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((e) => (
                <tr key={e.id}>
                  <td><a href={`#/hse/${e.id}`}>{e.numero}</a></td><td>{moment(e.date)}</td><td>{e.type_libelle}{e.jours_arret > 0 && <><br /><span className="aide">{e.jours_arret} j d'arrêt</span></>}</td>
                  <td>{[e.site_nom, e.lieu].filter(Boolean).join(' · ')}</td><td><span className={`pastille ${pastilleGravite(e.gravite)}`}>{e.gravite_libelle}</span></td>
                  <td>{e.actions.length ? `${e.actions.length - e.actions_a_faire} / ${e.actions.length}` : ''}</td>
                  <td><span className={`pastille ${pastille(e)}`}>{e.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireEvenement({ id }: { id?: number }) {
  const [s, setS] = useState({ type: 'PRESQUE', gravite: '1', date: maintenant(), site: '' as number | '', lieu: '', description: '', personnes: '', materiel: null as number | null, mesures_immediates: '', jours_arret: 0 })
  const [sites, setSites] = useState<Site[]>([])
  const [materiels, setMateriels] = useState<Materiel[]>([])
  const [pret, setPret] = useState(!id)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Materiel>>('/technique/materiels/?page_size=300').then((p) => setMateriels(p.results)).catch(() => undefined)
    if (id) api<Evenement>(`/hse/evenements/${id}/`).then((e) => {
      setS({ type: e.type, gravite: e.gravite, date: new Date(new Date(e.date).getTime() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16), site: e.site, lieu: e.lieu, description: e.description, personnes: e.personnes, materiel: e.materiel, mesures_immediates: e.mesures_immediates, jours_arret: e.jours_arret })
      setPret(true)
    }).catch((e: Error) => setErreur(e.message))
  }, [id])

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const corps = { ...s, date: new Date(s.date).toISOString(), jours_arret: s.type === 'ACCIDENT' ? s.jours_arret : 0 }
      const r = await api<Evenement>(id ? `/hse/evenements/${id}/` : '/hse/evenements/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      location.hash = `#/hse/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  if (!pret) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  return (
    <form className="fiche" onSubmit={envoyer}>
      <p><a href={id ? `#/hse/${id}` : '#/hse'}>← Retour</a></p>
      <h2>{id ? 'Corriger la déclaration' : 'Déclarer un événement'}</h2>
      <p className="aide">Déclarez aussi ce qui aurait pu mal tourner : un presqu'accident ou une situation dangereuse signalés évitent l'accident suivant.</p>
      <fieldset>
        <legend>Événement</legend>
        <div className="grille">
          <label>Type<select value={s.type} onChange={(e) => setS({ ...s, type: e.target.value })}>{TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Gravité<select value={s.gravite} onChange={(e) => setS({ ...s, gravite: e.target.value })}>{GRAVITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <label>Date et heure<input type="datetime-local" required max={maintenant()} value={s.date} onChange={(e) => setS({ ...s, date: e.target.value })} /></label>
          <label>Site<select required value={s.site} onChange={(e) => setS({ ...s, site: Number(e.target.value) || '' })}><option value="">Choisir</option>{sites.map((x) => <option key={x.id} value={x.id}>{x.nom}</option>)}</select></label>
          <label>Lieu précis<input maxLength={200} placeholder="Atelier, quai, chantier du client…" value={s.lieu} onChange={(e) => setS({ ...s, lieu: e.target.value })} /></label>
          <label>Matériel en cause<select value={s.materiel ?? ''} onChange={(e) => setS({ ...s, materiel: Number(e.target.value) || null })}><option value="">Aucun</option>{materiels.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}</option>)}</select></label>
          {s.type === 'ACCIDENT' && <label>Jours d'arrêt de travail<input type="number" min="0" max="3650" value={s.jours_arret} onChange={(e) => setS({ ...s, jours_arret: Number(e.target.value) })} /></label>}
        </div>
        <label>Ce qui s'est passé<textarea required rows={4} value={s.description} onChange={(e) => setS({ ...s, description: e.target.value })} /></label>
        <label>Personnes concernées<input maxLength={300} placeholder="Victime, témoins, entreprise extérieure" value={s.personnes} onChange={(e) => setS({ ...s, personnes: e.target.value })} /></label>
        <label>Mesures prises sur le moment<textarea value={s.mesures_immediates} onChange={(e) => setS({ ...s, mesures_immediates: e.target.value })} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions"><button disabled={enCours}>{id ? 'Enregistrer' : 'Envoyer la déclaration'}</button></div>
      {!id && <p className="aide">Vous pourrez joindre des photos une fois la déclaration envoyée.</p>}
    </form>
  )
}

export function DetailEvenement({ id }: { id: number }) {
  const [e, setE] = useState<Evenement | null>(null)
  const [comptes, setComptes] = useState<Compte[]>([])
  const [an, setAn] = useState({ causes: '', gravite: '1', jours_arret: 0, conclusion: '' })
  const [ac, setAc] = useState({ description: '', responsable: '', echeance: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const recevoir = useCallback((x: Evenement) => {
    setE(x)
    setAn({ causes: x.causes, gravite: x.gravite, jours_arret: x.jours_arret, conclusion: '' })
  }, [])
  const charger = useCallback(() => {
    api<Evenement>(`/hse/evenements/${id}/`).then(recevoir).catch((err: Error) => setErreur(err.message))
  }, [id, recevoir])
  useEffect(charger, [charger])
  useEffect(() => {
    if (e?.peut_traiter && comptes.length === 0) api<Page<Compte>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setComptes(p.results)).catch(() => undefined)
  }, [e?.peut_traiter, comptes.length])

  async function envoyer(chemin: string, corps: object) {
    setErreur('')
    setEnCours(true)
    try {
      await api(chemin, { method: 'POST', body: JSON.stringify(corps) })
      charger()
      return true
    } catch (err) {
      setErreur((err as Error).message)
      return false
    } finally {
      setEnCours(false)
    }
  }
  async function ajouterAction(ev: FormEvent) {
    ev.preventDefault()
    if (await envoyer('/hse/actions/', { evenement: id, ...ac, responsable: Number(ac.responsable) })) setAc({ description: '', responsable: '', echeance: '' })
  }
  const terminer = (a: Action) => { const c = prompt('Commentaire (facultatif) :', ''); if (c !== null) envoyer(`/hse/actions/${a.id}/terminer/`, { commentaire: c }) }
  const abandonner = (a: Action) => { const c = prompt("Pourquoi l'action est-elle abandonnée ?", ''); if (c) envoyer(`/hse/actions/${a.id}/abandonner/`, { commentaire: c }) }

  if (!e) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const ouvert = e.statut !== 'CLOS'
  return (
    <div className="fiche">
      <p><a href="#/hse">← Événements HSE</a></p>
      <div className="barre">
        <h2>{e.type_libelle} {e.numero}</h2>
        {e.peut_modifier && <div className="actions"><a className="bouton secondaire" href={`#/hse/${id}/modifier`}>Corriger</a></div>}
      </div>
      <p className="statut">{e.statut_libelle} · gravité {e.gravite_libelle.toLowerCase()}</p>
      <dl>
        <dt>Date</dt><dd>{moment(e.date)}</dd>
        <dt>Lieu</dt><dd>{[e.site_nom, e.lieu].filter(Boolean).join(' · ')}</dd>
        <dt>Faits</dt><dd style={{ whiteSpace: 'pre-line' }}>{e.description}</dd>
        {e.personnes && <><dt>Personnes</dt><dd>{e.personnes}</dd></>}
        {e.materiel_nom && <><dt>Matériel</dt><dd>{e.materiel_nom}</dd></>}
        {e.mesures_immediates && <><dt>Mesures</dt><dd style={{ whiteSpace: 'pre-line' }}>{e.mesures_immediates}</dd></>}
        {e.type === 'ACCIDENT' && <><dt>Arrêt</dt><dd>{e.jours_arret ? `${e.jours_arret} jour${e.jours_arret > 1 ? 's' : ''}` : 'sans arrêt de travail'}</dd></>}
        <dt>Déclaré par</dt><dd>{e.declarant_nom}</dd>
        {e.causes && !(e.peut_traiter && ouvert) && <><dt>Causes</dt><dd style={{ whiteSpace: 'pre-line' }}>{e.causes}</dd></>}
        {e.conclusion && <><dt>Conclusion</dt><dd style={{ whiteSpace: 'pre-line' }}>{e.conclusion}</dd></>}
        {e.clos_le && <><dt>Clos</dt><dd>le {dateFr(e.clos_le)} par {e.clos_par_nom}</dd></>}
      </dl>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {e.peut_traiter && ouvert && (
        <fieldset>
          <legend>Analyse</legend>
          <label>Causes de l'événement<textarea rows={4} placeholder="Causes immédiates et causes profondes" value={an.causes} onChange={(ev) => setAn({ ...an, causes: ev.target.value })} /></label>
          <div className="grille">
            <label>Gravité retenue<select value={an.gravite} onChange={(ev) => setAn({ ...an, gravite: ev.target.value })}>{GRAVITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            {e.type === 'ACCIDENT' && <label>Jours d'arrêt de travail<input type="number" min="0" max="3650" value={an.jours_arret} onChange={(ev) => setAn({ ...an, jours_arret: Number(ev.target.value) })} /></label>}
          </div>
          <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => envoyer(`/hse/evenements/${id}/analyser/`, { causes: an.causes, gravite: an.gravite, ...(e.type === 'ACCIDENT' ? { jours_arret: an.jours_arret } : {}) })}>Enregistrer l'analyse</button></div>
        </fieldset>
      )}

      {(e.actions.length > 0 || (e.peut_traiter && ouvert)) && (
        <fieldset>
          <legend>Actions correctives</legend>
          {e.actions.length === 0 && <p className="aide">Aucune action décidée.</p>}
          {e.actions.length > 0 && (
            <div className="defilant"><table>
              <thead><tr><th>Action</th><th>Responsable</th><th>Échéance</th><th>État</th><th></th></tr></thead>
              <tbody>{e.actions.map((a) => (
                <tr key={a.id}>
                  <td>{a.description}{a.commentaire && <><br /><span className="aide">{a.commentaire}</span></>}</td><td>{a.responsable_nom}</td>
                  <td>{dateFr(a.echeance)}</td>
                  <td><span className={`pastille ${a.statut === 'FAITE' ? 'complete' : a.en_retard ? 'u1' : a.statut === 'A_FAIRE' ? 'partielle' : ''}`}>{a.en_retard ? 'En retard' : a.statut_libelle}{a.faite_le ? ` le ${dateFr(a.faite_le)}` : ''}</span></td>
                  <td>{a.peut_agir && <button type="button" className="lien" disabled={enCours} onClick={() => terminer(a)}>Terminer</button>}{a.statut === 'A_FAIRE' && e.peut_traiter && <> <button type="button" className="lien" disabled={enCours} onClick={() => abandonner(a)}>Abandonner</button></>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          {e.peut_traiter && ouvert && (
            <form className="grille" onSubmit={ajouterAction}>
              <label>Action à mener<input required maxLength={300} value={ac.description} onChange={(ev) => setAc({ ...ac, description: ev.target.value })} /></label>
              <label>Responsable<select required value={ac.responsable} onChange={(ev) => setAc({ ...ac, responsable: ev.target.value })}><option value="">Choisir</option>{comptes.map((c) => <option key={c.id} value={c.id}>{[c.last_name, c.first_name].filter(Boolean).join(' ') || c.username}</option>)}</select></label>
              <label>À faire avant le<input type="date" required value={ac.echeance} onChange={(ev) => setAc({ ...ac, echeance: ev.target.value })} /></label>
              <div className="actions"><button className="secondaire" disabled={enCours}>Ajouter l'action</button></div>
            </form>
          )}
        </fieldset>
      )}

      {e.peut_traiter && e.statut === 'ANALYSE' && (
        <fieldset>
          <legend>Clôture</legend>
          <p className="aide">L'événement se clôt quand toutes les actions sont faites ou abandonnées.</p>
          <label>Conclusion<textarea value={an.conclusion} onChange={(ev) => setAn({ ...an, conclusion: ev.target.value })} /></label>
          <div className="actions"><button disabled={enCours} onClick={() => envoyer(`/hse/evenements/${id}/clore/`, { conclusion: an.conclusion })}>Clore l'événement</button></div>
        </fieldset>
      )}
      {e.peut_traiter && !ouvert && <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => envoyer(`/hse/evenements/${id}/rouvrir/`, {})}>Rouvrir</button></div>}
      <PiecesJointes modele="hse.evenement" objet={id} aide="Joignez ici les photos, le constat ou le certificat médical." />
    </div>
  )
}
