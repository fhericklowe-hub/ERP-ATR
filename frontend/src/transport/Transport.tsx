import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site, type Tiers } from '../api'
import BoutonExcel from '../BoutonExcel'
import PiecesJointes from '../PiecesJointes'
import { montant } from '../achats/commandes'
import { dateFr, dateHeureFr } from '../achats/types'
import { nombre } from '../stock/types'

type Ordre = {
  id: number; numero: string; statut: string; statut_libelle: string; client: number; client_nom: string; reference_client: string
  site: number; site_nom: string; origine: string; destination: string; marchandise: string; poids_tonnes: string | null; nombre_colis: number | null
  date_prevue: string; tracteur: number; tracteur_nom: string; tracteur_compteur_km: number | null; remorque: number | null; remorque_nom: string
  chauffeur: string; prix_ht: string | null; observations: string; depart_le: string | null; km_depart: number | null; arrivee_le: string | null
  km_arrivee: number | null; carburant_litres: string | null; km_parcourus: number | null; consommation_100km: string | null; reserves: string
  motif_annulation: string; peut_agir: boolean
}
type Engin = { id: number; code: string; designation: string; etat: string }
type Groupe = { nom: string; ordres: number; km: number; litres: string; consommation_100km: string | null }
type Synthese = { ordres: number; par_tracteur: Groupe[]; par_chauffeur: Groupe[] }

const STATUTS = [['', 'Tous'], ['PLANIFIE', 'Planifiés'], ['EN_COURS', 'En route'], ['LIVRE', 'Livrés'], ['ANNULE', 'Annulés']]
const pastille = (o: Ordre) => (o.statut === 'EN_COURS' ? 'partielle' : o.statut === 'LIVRE' ? 'complete' : o.statut === 'PLANIFIE' ? 'u3' : '')
const maintenant = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16)
const jour = (d: Date) => d.toLocaleDateString('fr-CA')
const BASE = '/transport/ordres/'

export function ListeTransports({ peutCreer }: { peutCreer: boolean }) {
  const [liste, setListe] = useState<Ordre[] | null>(null)
  const [filtre, setFiltre] = useState({ search: '', statut: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Page<Ordre>>(`${BASE}?${new URLSearchParams(filtre)}&page_size=100`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre">
        <h2>Ordres de transport</h2>
        <div className="actions">
          <BoutonExcel chemin={BASE} filtres={filtre} nom="ordres-transport" onErreur={setErreur} />
          {peutCreer && <a className="bouton" href="#/transports/nouveau">Nouvel ordre</a>}
        </div>
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="N°, client, lieu, chauffeur, tracteur" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>État<select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>{STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p className="aide">Aucun ordre de transport.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Client</th><th>Trajet</th><th>Départ prévu</th><th>Tracteur et chauffeur</th><th>État</th></tr></thead>
            <tbody>
              {liste.map((o) => (
                <tr key={o.id}>
                  <td><a href={`#/transports/${o.id}`}>{o.numero}</a></td>
                  <td>{o.client_nom}{o.reference_client && <><br /><span className="aide">{o.reference_client}</span></>}</td>
                  <td>{o.origine} → {o.destination}</td>
                  <td>{dateFr(o.date_prevue)}</td>
                  <td>{o.tracteur_nom}<br /><span className="aide">{o.chauffeur}</span></td>
                  <td><span className={`pastille ${pastille(o)}`}>{o.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireTransport() {
  const [clients, setClients] = useState<Tiers[]>([])
  const [sites, setSites] = useState<Site[]>([])
  const [engins, setEngins] = useState<Record<string, Engin[]>>({ TRACTEUR: [], CAMION: [], REMORQUE: [] })
  const [f, setF] = useState({ client: '', reference_client: '', site: '', origine: '', destination: '', marchandise: '', poids_tonnes: '', nombre_colis: '', date_prevue: jour(new Date()), tracteur: '', remorque: '', chauffeur: '', prix_ht: '', observations: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    api<Page<Tiers>>('/tiers/?est_client=true&actif=true&page_size=500').then((p) => setClients(p.results)).catch(() => undefined)
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    for (const type of ['TRACTEUR', 'CAMION', 'REMORQUE']) {
      api<Page<Engin>>(`/technique/materiels/?type=${type}&page_size=500`).then((p) => setEngins((e) => ({ ...e, [type]: p.results.filter((m) => m.etat !== 'REFORME') }))).catch(() => undefined)
    }
  }, [])
  const maj = (c: string, v: string) => setF({ ...f, [c]: v })
  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setEnCours(true)
    setErreur('')
    try {
      const o = await api<Ordre>(BASE, { method: 'POST', body: JSON.stringify({ ...f, remorque: f.remorque || null, poids_tonnes: f.poids_tonnes || null, nombre_colis: f.nombre_colis || null, prix_ht: f.prix_ht || null }) })
      location.hash = `#/transports/${o.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  const tracteurs = [...engins.TRACTEUR, ...engins.CAMION]
  return (
    <form className="fiche" onSubmit={envoyer}>
      <p><a href="#/transports">← Ordres de transport</a></p>
      <h2>Nouvel ordre de transport</h2>
      <fieldset>
        <legend>Client et marchandise</legend>
        <div className="grille">
          <label>Client<select required value={f.client} onChange={(e) => maj('client', e.target.value)}><option value="">Choisir…</option>{clients.map((c) => <option key={c.id} value={c.id}>{c.raison_sociale}</option>)}</select></label>
          <label>Référence du client (BL, booking, conteneur)<input maxLength={80} value={f.reference_client} onChange={(e) => maj('reference_client', e.target.value)} /></label>
          <label>Agence<select required value={f.site} onChange={(e) => maj('site', e.target.value)}><option value="">Choisir…</option>{sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}</select></label>
          <label>Marchandise<input maxLength={200} value={f.marchandise} onChange={(e) => maj('marchandise', e.target.value)} /></label>
          <label>Poids (tonnes)<input type="number" min="0" step="0.01" value={f.poids_tonnes} onChange={(e) => maj('poids_tonnes', e.target.value)} /></label>
          <label>Conteneurs ou colis<input type="number" min="0" step="1" value={f.nombre_colis} onChange={(e) => maj('nombre_colis', e.target.value)} /></label>
          <label>Prix du transport HT (XOF, facultatif)<input type="number" min="0" step="1" value={f.prix_ht} onChange={(e) => maj('prix_ht', e.target.value)} /></label>
        </div>
      </fieldset>
      <fieldset>
        <legend>Trajet et moyens</legend>
        <div className="grille">
          <label>Lieu de chargement<input required maxLength={200} value={f.origine} onChange={(e) => maj('origine', e.target.value)} /></label>
          <label>Lieu de livraison<input required maxLength={200} value={f.destination} onChange={(e) => maj('destination', e.target.value)} /></label>
          <label>Départ prévu le<input type="date" required value={f.date_prevue} onChange={(e) => maj('date_prevue', e.target.value)} /></label>
          <label>Tracteur ou camion<select required value={f.tracteur} onChange={(e) => maj('tracteur', e.target.value)}><option value="">Choisir…</option>{tracteurs.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}</option>)}</select></label>
          <label>Remorque<select value={f.remorque} onChange={(e) => maj('remorque', e.target.value)}><option value="">Sans remorque</option>{engins.REMORQUE.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}</option>)}</select></label>
          <label>Chauffeur<input required maxLength={120} value={f.chauffeur} onChange={(e) => maj('chauffeur', e.target.value)} /></label>
        </div>
        <label>Observations<textarea value={f.observations} onChange={(e) => maj('observations', e.target.value)} /></label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions"><button disabled={enCours}>Enregistrer l'ordre</button></div>
    </form>
  )
}

export function DetailTransport({ id }: { id: number }) {
  const [o, setO] = useState<Ordre | null>(null)
  const [s, setS] = useState({ moment: maintenant(), km: '', litres: '', reserves: '', motif: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const charger = useCallback(() => { api<Ordre>(`${BASE}${id}/`).then(setO).catch((e: Error) => setErreur(e.message)) }, [id])
  useEffect(charger, [charger])
  async function agir(action: string, corps: object) {
    setEnCours(true)
    setErreur('')
    try {
      setO(await api<Ordre>(`${BASE}${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setS({ moment: maintenant(), km: '', litres: '', reserves: '', motif: '' })
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  if (!o) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const moment = () => (s.moment ? new Date(s.moment).toISOString() : '')
  return (
    <div className="fiche">
      <p><a href="#/transports">← Ordres de transport</a></p>
      <h2>Ordre de transport {o.numero}</h2>
      <p className="statut">{o.statut_libelle}</p>
      <dl>
        <dt>Client</dt><dd><strong>{o.client_nom}</strong>{o.reference_client && ` · ${o.reference_client}`}</dd>
        <dt>Trajet</dt><dd>{o.origine} → {o.destination}</dd>
        <dt>Départ prévu</dt><dd>le {dateFr(o.date_prevue)} · agence {o.site_nom}</dd>
        {(o.marchandise || o.poids_tonnes || o.nombre_colis) && <><dt>Marchandise</dt><dd>{[o.marchandise, o.poids_tonnes && `${nombre(o.poids_tonnes)} t`, o.nombre_colis && `${o.nombre_colis} conteneur(s) ou colis`].filter(Boolean).join(' · ')}</dd></>}
        <dt>Tracteur</dt><dd><a href={`#/parc/${o.tracteur}`}>{o.tracteur_nom}</a>{o.remorque && <> · remorque <a href={`#/parc/${o.remorque}`}>{o.remorque_nom}</a></>}</dd>
        <dt>Chauffeur</dt><dd>{o.chauffeur}</dd>
        {o.prix_ht && <><dt>Prix HT</dt><dd>{montant(o.prix_ht)}</dd></>}
        {o.observations && <><dt>Observations</dt><dd style={{ whiteSpace: 'pre-line' }}>{o.observations}</dd></>}
        {o.depart_le && <><dt>Départ</dt><dd>le {dateHeureFr(o.depart_le)} · compteur {nombre(o.km_depart ?? 0)} km</dd></>}
        {o.arrivee_le && <><dt>Livraison</dt><dd>le {dateHeureFr(o.arrivee_le)} · compteur {nombre(o.km_arrivee ?? 0)} km</dd></>}
        {o.km_parcourus !== null && <><dt>Parcouru</dt><dd><strong>{nombre(o.km_parcourus)} km</strong>{o.carburant_litres && ` · ${nombre(o.carburant_litres)} l de carburant`}{o.consommation_100km && ` · ${nombre(o.consommation_100km)} l/100 km`}</dd></>}
        {o.statut === 'LIVRE' && <><dt>Réserves</dt><dd style={{ whiteSpace: 'pre-line' }}>{o.reserves || 'Aucune'}</dd></>}
        {o.motif_annulation && <><dt>Annulation</dt><dd>{o.motif_annulation}</dd></>}
      </dl>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {o.peut_agir && o.statut === 'PLANIFIE' && (
        <fieldset>
          <legend>Départ</legend>
          <div className="grille">
            <label>Date et heure<input type="datetime-local" max={maintenant()} value={s.moment} onChange={(e) => setS({ ...s, moment: e.target.value })} /></label>
            <label>Compteur du tracteur (km)<input type="number" min="0" step="1" placeholder={o.tracteur_compteur_km ? `dernier relevé : ${nombre(o.tracteur_compteur_km)}` : ''} value={s.km} onChange={(e) => setS({ ...s, km: e.target.value })} /></label>
          </div>
          <div className="actions"><button disabled={enCours} onClick={() => agir('demarrer', { moment: moment(), km: s.km })}>Enregistrer le départ</button></div>
        </fieldset>
      )}
      {o.peut_agir && o.statut === 'EN_COURS' && (
        <fieldset>
          <legend>Livraison</legend>
          <div className="grille">
            <label>Date et heure<input type="datetime-local" max={maintenant()} value={s.moment} onChange={(e) => setS({ ...s, moment: e.target.value })} /></label>
            <label>Compteur à l'arrivée (km)<input type="number" min={o.km_depart ?? 0} step="1" value={s.km} onChange={(e) => setS({ ...s, km: e.target.value })} /></label>
            <label>Carburant consommé (litres, facultatif)<input type="number" min="0" step="0.1" value={s.litres} onChange={(e) => setS({ ...s, litres: e.target.value })} /></label>
          </div>
          <label>Réserves à la livraison (laisser vide s'il n'y en a pas)<textarea value={s.reserves} onChange={(e) => setS({ ...s, reserves: e.target.value })} /></label>
          <div className="actions"><button disabled={enCours} onClick={() => agir('livrer', { moment: moment(), km: s.km, litres: s.litres, reserves: s.reserves })}>Enregistrer la livraison</button></div>
        </fieldset>
      )}
      {o.peut_agir && (o.statut === 'PLANIFIE' || o.statut === 'EN_COURS') && (
        <fieldset>
          <legend>Annulation</legend>
          <label>Motif<textarea value={s.motif} onChange={(e) => setS({ ...s, motif: e.target.value })} /></label>
          <div className="actions"><button className="danger" disabled={enCours} onClick={() => agir('annuler', { motif: s.motif })}>Annuler l'ordre</button></div>
        </fieldset>
      )}
      <PiecesJointes modele="transport.ordretransport" objet={id} aide="Joignez ici la lettre de voiture, le bon de livraison signé et les tickets de carburant." />
    </div>
  )
}

function TableauGroupe({ titre, lignes }: { titre: string; lignes: Groupe[] }) {
  return (
    <div className="defilant">
      <table>
        <thead><tr><th>{titre}</th><th className="nombre">Trajets</th><th className="nombre">Km</th><th className="nombre">Carburant (l)</th><th className="nombre">l/100 km</th></tr></thead>
        <tbody>{lignes.map((l) => <tr key={l.nom}><td>{l.nom}</td><td className="nombre">{l.ordres}</td><td className="nombre">{nombre(l.km)}</td><td className="nombre">{nombre(l.litres)}</td><td className="nombre">{l.consommation_100km ? nombre(l.consommation_100km) : '–'}</td></tr>)}</tbody>
      </table>
    </div>
  )
}

export function SyntheseTransport() {
  const [filtre, setFiltre] = useState({ debut: jour(new Date(new Date().getFullYear(), new Date().getMonth(), 1)), fin: jour(new Date()) })
  const [res, setRes] = useState<Synthese | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Synthese>(`${BASE}synthese/?${new URLSearchParams(filtre)}`).then((r) => { setRes(r); setErreur('') }).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  return (
    <>
      <div className="barre"><h2>Kilomètres et carburant</h2></div>
      <p className="aide">Ordres livrés sur la période. La consommation ne porte que sur les trajets où le carburant a été saisi.</p>
      <div className="grille filtres">
        <label>Du<input type="date" value={filtre.debut} onChange={(e) => setFiltre({ ...filtre, debut: e.target.value })} /></label>
        <label>Au<input type="date" value={filtre.fin} onChange={(e) => setFiltre({ ...filtre, fin: e.target.value })} /></label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {res && res.ordres === 0 && <p className="aide">Aucun ordre livré sur cette période.</p>}
      {res && res.ordres > 0 && (
        <>
          <h3>Par tracteur</h3><TableauGroupe titre="Tracteur" lignes={res.par_tracteur} />
          <h3>Par chauffeur</h3><TableauGroupe titre="Chauffeur" lignes={res.par_chauffeur} />
        </>
      )}
    </>
  )
}
