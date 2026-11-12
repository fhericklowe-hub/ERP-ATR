import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Service, type Utilisateur } from '../api'
import PiecesJointes from '../PiecesJointes'
import { dateHeureFr } from '../achats/types'
import { type Magasin, nombre } from './types'

type Article = { id: number; code: string; designation: string; nature: string }
type Ligne = { id: number; article: number; code: string; designation: string; unite: string; quantite: string; quantite_servie: string; en_stock: string | null }
type Demande = {
  id: number
  numero: string
  statut: string
  statut_libelle: string
  cree_le: string
  demandeur_nom: string
  service_nom: string
  magasin_nom: string
  numero_or: string
  materiel: string
  motif: string
  valide_par_nom: string
  traite_par_nom: string
  traite_le: string | null
  motif_refus: string
  bon_sortie: number | null
  bon_sortie_numero: string
  peut_valider: boolean
  peut_servir: boolean
  peut_refuser: boolean
  peut_annuler: boolean
  lignes: Ligne[]
}

const STATUTS = [['', 'Toutes'], ['ATT_SERVICE', 'À valider par le service'], ['A_SERVIR', 'À servir'], ['SERVIE', 'Servies'], ['REFUSEE', 'Refusées'], ['ANNULEE', 'Annulées']]
const pastille = (s: string) => (s === 'SERVIE' ? 'complete' : s === 'A_SERVIR' ? 'partielle' : s === 'ATT_SERVICE' ? 'u3' : '')

export function ListeDemandes() {
  const [demandes, setDemandes] = useState<Demande[] | null>(null)
  const [statut, setStatut] = useState('')
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Page<Demande>>(`/stock/demandes/?statut=${statut}`).then((p) => setDemandes(p.results)).catch((e: Error) => setErreur(e.message))
  }, [statut])

  return (
    <>
      <div className="barre">
        <h2>Demandes de sortie de stock</h2>
        <a className="bouton" href="#/stock/demandes/nouvelle">Nouvelle demande</a>
      </div>
      <label className="filtre">Afficher
        <select value={statut} onChange={(e) => setStatut(e.target.value)}>
          {STATUTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </label>
      {erreur && <p className="erreur">{erreur}</p>}
      {!demandes && !erreur && <p>Chargement…</p>}
      {demandes?.length === 0 && <p>Aucune demande.</p>}
      {demandes && demandes.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Date</th><th>Demandeur</th><th>OR / usage</th><th>Articles</th><th>État</th></tr></thead>
            <tbody>
              {demandes.map((d) => (
                <tr key={d.id}>
                  <td><a href={`#/stock/demandes/${d.id}`}>{d.numero}</a></td>
                  <td>{dateHeureFr(d.cree_le)}</td>
                  <td>{d.demandeur_nom}<br /><span className="aide">{d.service_nom} · {d.magasin_nom}</span></td>
                  <td>{[d.numero_or, d.materiel, d.motif].filter(Boolean).join(' · ')}</td>
                  <td>{d.lignes.map((l) => `${nombre(l.quantite)} ${l.designation}`).join(', ')}</td>
                  <td><span className={`pastille ${pastille(d.statut)}`}>{d.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireDemande({ moi, numeroOr, materiel }: { moi: Utilisateur; numeroOr?: string; materiel?: string }) {
  const [magasins, setMagasins] = useState<Magasin[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [d, setD] = useState({ service: moi.service ? String(moi.service) : '', magasin: '', numero_or: numeroOr ?? '', materiel: materiel ?? '', motif: '' })
  const [recherche, setRecherche] = useState('')
  const [trouves, setTrouves] = useState<Article[]>([])
  const [lignes, setLignes] = useState<{ article: Article; quantite: string }[]>([])
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api<Page<Magasin>>('/emplacements/?type=SITE&actif=true').then((p) => setMagasins(p.results)).catch(() => undefined)
    api<Page<Service>>('/services/?actif=true').then((p) => setServices(p.results)).catch(() => undefined)
  }, [])
  const [ordres, setOrdres] = useState<{ numero: string; materiel_nom: string }[]>([])
  useEffect(() => {
    // Les ordres de réparation ouverts, proposés à la saisie du n° d'OR. Sans le droit de les voir, la saisie reste libre.
    api<Page<{ numero: string; materiel_nom: string }>>('/technique/ordres/?ouvert=1&page_size=200').then((p) => setOrdres(p.results)).catch(() => undefined)
  }, [])
  useEffect(() => {
    if (recherche.length < 2) return setTrouves([])
    const t = setTimeout(() => {
      api<Page<Article>>(`/articles/?gere_en_stock=true&actif=true&search=${encodeURIComponent(recherche)}`).then((p) => setTrouves(p.results)).catch(() => undefined)
    }, 250)
    return () => clearTimeout(t)
  }, [recherche])

  const champ = (k: keyof typeof d, v: string) => setD((x) => ({ ...x, [k]: v }))
  const piece = lignes.some((l) => l.article.nature === 'PIECE')

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    if (lignes.length === 0) return setErreur('Ajoutez au moins un article.')
    setErreur('')
    setEnCours(true)
    try {
      const r = await api<Demande>('/stock/demandes/', {
        method: 'POST', body: JSON.stringify({ ...d, lignes: lignes.map((l) => ({ article: l.article.id, quantite: l.quantite })) }),
      })
      location.hash = `#/stock/demandes/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={envoyer}>
      <h2>Nouvelle demande de sortie de stock</h2>
      <fieldset>
        <legend>Articles</legend>
        <label>Chercher un article (code ou désignation)
          <input value={recherche} placeholder="Exemple : filtre, papier A4" onChange={(e) => setRecherche(e.target.value)} />
        </label>
        {trouves.filter((a) => !lignes.some((l) => l.article.id === a.id)).slice(0, 8).map((a) => (
          <div className="actions" key={a.id}>
            <button type="button" className="secondaire" onClick={() => { setLignes([...lignes, { article: a, quantite: '1' }]); setRecherche('') }}>Ajouter</button>
            <span>{a.code} · {a.designation}</span>
          </div>
        ))}
        {recherche.length >= 2 && trouves.length === 0 && <p className="aide">Aucun article trouvé.</p>}
        {lignes.map((l, i) => (
          <div className="ligne sortie" key={l.article.id}>
            <div><strong>{l.article.designation}</strong><br /><span className="aide">{l.article.code}</span></div>
            <label>Quantité
              <input type="number" required min="0.01" step="0.01" value={l.quantite} onChange={(e) => setLignes(lignes.map((x, j) => (j === i ? { ...x, quantite: e.target.value } : x)))} />
            </label>
            <button type="button" className="discret" onClick={() => setLignes(lignes.filter((_, j) => j !== i))}>Retirer</button>
          </div>
        ))}
      </fieldset>
      <fieldset>
        <legend>Pour quel usage</legend>
        <div className="grille">
          <label>N° d'OR {piece ? '(obligatoire pour une pièce)' : '(pour une pièce)'}
            <input required={piece} value={d.numero_or} maxLength={40} list="ordres-ouverts" onChange={(e) => {
              const ordre = ordres.find((o) => o.numero === e.target.value)
              setD((x) => ({ ...x, numero_or: e.target.value, materiel: ordre && !x.materiel ? ordre.materiel_nom : x.materiel }))
            }} />
            <datalist id="ordres-ouverts">{ordres.map((o) => <option key={o.numero} value={o.numero}>{o.materiel_nom}</option>)}</datalist>
          </label>
          <label>Matériel concerné
            <input value={d.materiel} placeholder="Engin, véhicule, immatriculation" onChange={(e) => champ('materiel', e.target.value)} />
          </label>
          <label>Service
            <select required value={d.service} onChange={(e) => champ('service', e.target.value)}>
              <option value="">Choisir…</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Magasin
            <select required value={d.magasin} onChange={(e) => champ('magasin', e.target.value)}>
              <option value="">Choisir…</option>
              {magasins.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
            </select>
          </label>
        </div>
        <label>Motif ou usage (facultatif)
          <input value={d.motif} maxLength={200} placeholder="Exemple : fournitures du mois pour le bureau commercial" onChange={(e) => champ('motif', e.target.value)} />
        </label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Envoi…' : 'Envoyer la demande'}</button>
        <a href="#/stock/demandes">Annuler</a>
      </div>
    </form>
  )
}

export function DetailDemande({ id }: { id: number }) {
  const [d, setD] = useState<Demande | null>(null)
  const [servi, setServi] = useState<Record<number, string>>({})
  const [motif, setMotif] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const recevoir = useCallback((x: Demande) => {
    setD(x)
    // Par défaut, le magasin sert ce qui est demandé, dans la limite du stock.
    setServi(Object.fromEntries(x.lignes.map((l) => [l.id, String(Math.min(Number(l.quantite), Math.max(0, Number(l.en_stock ?? l.quantite))))])))
  }, [])
  useEffect(() => {
    api<Demande>(`/stock/demandes/${id}/`).then(recevoir).catch((e: Error) => setErreur(e.message))
  }, [id, recevoir])

  async function agir(action: string, corps: object = {}) {
    setErreur('')
    setEnCours(true)
    try {
      recevoir(await api<Demande>(`/stock/demandes/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setMotif('')
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (!d) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const fermee = d.statut === 'REFUSEE' || d.statut === 'ANNULEE'
  return (
    <div className="fiche">
      <p><a href="#/stock/demandes">← Demandes de sortie</a></p>
      <div className="barre"><h2>{d.numero}</h2></div>
      <p className="statut">{d.statut_libelle}</p>
      <dl>
        <dt>Demandeur</dt><dd>{d.demandeur_nom} · {d.service_nom} · le {dateHeureFr(d.cree_le)}</dd>
        <dt>Magasin</dt><dd>{d.magasin_nom}</dd>
        {d.numero_or && <><dt>N° d'OR</dt><dd><strong>{d.numero_or}</strong></dd></>}
        {d.materiel && <><dt>Matériel</dt><dd>{d.materiel}</dd></>}
        {d.motif && <><dt>Usage</dt><dd>{d.motif}</dd></>}
        {d.valide_par_nom && <><dt>Validée par</dt><dd>{d.valide_par_nom}</dd></>}
        {d.bon_sortie && <><dt>Bon de sortie</dt><dd><a href={`#/stock/sorties/${d.bon_sortie}`}>{d.bon_sortie_numero}</a> · servi par {d.traite_par_nom}, le {dateHeureFr(d.traite_le ?? '')}</dd></>}
        {fermee && <><dt>{d.statut === 'REFUSEE' ? 'Refus' : 'Annulation'}</dt><dd>{d.motif_refus} ({d.traite_par_nom})</dd></>}
      </dl>
      <div className="defilant">
        <table>
          <thead>
            <tr>
              <th>Article</th><th className="nombre">Demandé</th>
              {d.peut_servir && <><th className="nombre">En stock</th><th className="nombre">À servir</th></>}
              {d.statut === 'SERVIE' && <th className="nombre">Servi</th>}
            </tr>
          </thead>
          <tbody>
            {d.lignes.map((l) => (
              <tr key={l.id}>
                <td>{l.designation}<br /><span className="aide">{l.code}</span></td>
                <td className="nombre">{nombre(l.quantite)} {l.unite}</td>
                {d.peut_servir && (
                  <>
                    <td className={`nombre ${Number(l.en_stock) < Number(l.quantite) ? 'erreur' : ''}`}>{nombre(l.en_stock ?? 0)}</td>
                    <td className="nombre">
                      <input aria-label={`À servir : ${l.designation}`} type="number" min="0" step="0.01" max={l.quantite} value={servi[l.id] ?? ''} style={{ width: 110, display: 'inline-block' }}
                        onChange={(e) => setServi({ ...servi, [l.id]: e.target.value })} />
                    </td>
                  </>
                )}
                {d.statut === 'SERVIE' && <td className="nombre">{nombre(l.quantite_servie)} {l.unite}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        {d.peut_valider && <button disabled={enCours} onClick={() => agir('valider')}>Valider la demande</button>}
        {d.peut_servir && <button disabled={enCours} onClick={() => agir('servir', { quantites: servi })}>Servir et créer le bon de sortie</button>}
      </div>
      {d.peut_servir && <p className="aide">Ce qui n'est pas servi aujourd'hui fera l'objet d'une nouvelle demande.</p>}
      {(d.peut_refuser || d.peut_annuler) && (
        <fieldset>
          <legend>{d.peut_refuser ? 'Refuser' : 'Annuler ma demande'}</legend>
          <label>Motif
            <textarea value={motif} onChange={(e) => setMotif(e.target.value)} />
          </label>
          <div className="actions">
            {d.peut_refuser && <button className="danger" disabled={enCours} onClick={() => agir('refuser', { commentaire: motif })}>Refuser la demande</button>}
            {d.peut_annuler && <button className="secondaire" disabled={enCours} onClick={() => agir('annuler', { commentaire: motif })}>Annuler ma demande</button>}
          </div>
        </fieldset>
      )}
      <PiecesJointes modele="stock.demandesortie" objet={id} />
    </div>
  )
}
