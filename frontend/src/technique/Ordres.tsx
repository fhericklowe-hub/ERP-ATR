import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import PiecesJointes from '../PiecesJointes'
import { montant as enChiffres } from '../achats/commandes'
import { dateFr, dateHeureFr } from '../achats/types'
import { nombre } from '../stock/types'
import { type Materiel, type Ordre, STATUTS_ORDRE, TYPES_ORDRE } from './types'
import BoutonExcel from '../BoutonExcel'

type Personne = { id: number; first_name: string; last_name: string; username: string }
const montant = (n: string) => `${enChiffres(n)} XOF`
const aujourdhui = () => new Date().toLocaleDateString('fr-CA')
const pastille = (s: string) => (s === 'CLOTURE' ? 'complete' : s === 'EN_COURS' ? 'partielle' : s === 'OUVERT' ? 'u1' : s === 'TERMINE' ? 'u3' : '')

export function ListeOrdres({ materiel, peutCreer }: { materiel?: string; peutCreer: boolean }) {
  const [ordres, setOrdres] = useState<Ordre[] | null>(null)
  const [filtre, setFiltre] = useState({ statut: '', search: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    const q = new URLSearchParams(filtre)
    if (materiel) q.set('materiel', materiel)
    const t = setTimeout(() => {
      api<Page<Ordre>>(`/technique/ordres/?${q}`).then((p) => setOrdres(p.results)).catch((e: Error) => setErreur(e.message))
    }, 200)
    return () => clearTimeout(t)
  }, [filtre, materiel])

  return (
    <>
      <div className="barre">
        <h2>Ordres de réparation</h2>
        <div className="actions">
          <BoutonExcel chemin="/technique/ordres/" nom="ordres-reparation" filtres={{ ...filtre, materiel: materiel ?? '' }} onErreur={setErreur} />
          <a className="bouton secondaire" href="#/parc">Parc de matériels</a>
          {peutCreer && <a className="bouton" href={`#/ordres/nouveau${materiel ? `?materiel=${materiel}` : ''}`}>Nouvel OR</a>}
        </div>
      </div>
      <div className="grille filtres">
        <label>Recherche
          <input value={filtre.search} placeholder="N° d'OR, matériel, panne" onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} />
        </label>
        <label>État
          <select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>
            {STATUTS_ORDRE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {materiel && <p className="aide">Ordres d'un seul matériel. <a href="#/ordres">Voir tous les ordres</a></p>}
      {erreur && <p className="erreur">{erreur}</p>}
      {!ordres && !erreur && <p>Chargement…</p>}
      {ordres?.length === 0 && <p>Aucun ordre de réparation.</p>}
      {ordres && ordres.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Ouvert le</th><th>Matériel</th><th>Travaux</th><th>Mécanicien</th><th>État</th></tr></thead>
            <tbody>
              {ordres.map((o) => (
                <tr key={o.id}>
                  <td><a href={`#/ordres/${o.id}`}>{o.numero}</a></td>
                  <td>{dateFr(o.cree_le)}</td>
                  <td>{o.materiel_nom}<br /><span className="aide">{o.site_nom}</span></td>
                  <td>{o.description}<br /><span className="aide">{o.type_libelle}</span></td>
                  <td>{o.mecanicien_nom}</td>
                  <td><span className={`pastille ${pastille(o.statut)}`}>{o.statut_libelle}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function FormulaireOrdre({ materiel }: { materiel?: string }) {
  const [materiels, setMateriels] = useState<Materiel[]>([])
  const [d, setD] = useState({ materiel: materiel ?? '', type: 'CORRECTIF', immobilisant: true, description: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  useEffect(() => {
    api<Page<Materiel>>('/technique/materiels/?page_size=200').then((p) => setMateriels(p.results.filter((m) => m.etat !== 'REFORME'))).catch(() => undefined)
  }, [])

  async function envoyer(e: FormEvent) {
    e.preventDefault()
    setErreur('')
    setEnCours(true)
    try {
      const r = await api<Ordre>('/technique/ordres/', { method: 'POST', body: JSON.stringify(d) })
      location.hash = `#/ordres/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={envoyer}>
      <h2>Nouvel ordre de réparation</h2>
      <fieldset>
        <div className="grille">
          <label>Matériel
            <select required value={d.materiel} onChange={(e) => setD({ ...d, materiel: e.target.value })}>
              <option value="">Choisir…</option>
              {materiels.map((m) => <option key={m.id} value={m.id}>{m.code} · {m.designation}{m.immatriculation && ` · ${m.immatriculation}`}</option>)}
            </select>
          </label>
          <label>Type
            <select value={d.type} onChange={(e) => setD({ ...d, type: e.target.value, immobilisant: e.target.value !== 'PREVENTIF' && e.target.value !== 'AMELIO' })}>
              {TYPES_ORDRE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
        </div>
        <label>Panne constatée ou travaux demandés
          <textarea required value={d.description} onChange={(e) => setD({ ...d, description: e.target.value })} />
        </label>
        <label className="case">
          <input type="checkbox" checked={d.immobilisant} onChange={(e) => setD({ ...d, immobilisant: e.target.checked })} />
          Le matériel est immobilisé (il passe « en panne » dans le parc)
        </label>
      </fieldset>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Ouverture…' : "Ouvrir l'ordre de réparation"}</button>
        <a href="#/ordres">Annuler</a>
      </div>
    </form>
  )
}

export function DetailOrdre({ id, peutDemanderPieces }: { id: number; peutDemanderPieces: boolean }) {
  const [o, setO] = useState<Ordre | null>(null)
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [s, setS] = useState({ diagnostic: '', travaux: '', compteur_heures: '', compteur_km: '', commentaire: '', mecanicien: '' })
  const [t, setT] = useState({ date: aujourdhui(), heures: '', mecanicien: '', commentaire: '' })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const recevoir = useCallback((x: Ordre) => {
    setO(x)
    setS((v) => ({ ...v, diagnostic: x.diagnostic, mecanicien: x.mecanicien ? String(x.mecanicien) : '', commentaire: '' }))
  }, [])
  useEffect(() => {
    api<Ordre>(`/technique/ordres/${id}/`).then((x) => {
      recevoir(x)
      if (x.peut_piloter) api<Page<Personne>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
    }).catch((e: Error) => setErreur(e.message))
  }, [id, recevoir])

  async function agir(action: string, corps: object = {}) {
    setErreur('')
    setEnCours(true)
    try {
      recevoir(await api<Ordre>(`/technique/ordres/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      if (action === 'saisir_temps') setT((v) => ({ ...v, heures: '', commentaire: '' }))
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (!o) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const ouvert = o.statut === 'OUVERT' || o.statut === 'EN_COURS'
  const compteurs = (
    <div className="grille">
      <label>Compteur relevé (heures)
        <input type="number" min="0" step="0.1" value={s.compteur_heures} onChange={(e) => setS({ ...s, compteur_heures: e.target.value })} />
      </label>
      <label>Compteur relevé (km)
        <input type="number" min="0" step="1" value={s.compteur_km} onChange={(e) => setS({ ...s, compteur_km: e.target.value })} />
      </label>
    </div>
  )
  return (
    <div className="fiche">
      <p><a href="#/ordres">← Ordres de réparation</a></p>
      <div className="barre"><h2>{o.numero}</h2></div>
      <p className="statut">{o.statut_libelle}</p>
      <dl>
        <dt>Matériel</dt><dd><strong>{o.materiel_nom}</strong> · {o.site_nom}</dd>
        <dt>Type</dt><dd>{o.type_libelle}{o.immobilisant ? ' · matériel immobilisé' : ''}{o.plan_intitule && <> · <a href="#/entretien">plan d'entretien</a></>}</dd>
        <dt>Demande</dt><dd style={{ whiteSpace: 'pre-line' }}>{o.description}</dd>
        <dt>Ouvert par</dt><dd>{o.demandeur_nom}, le {dateHeureFr(o.cree_le)}</dd>
        {o.mecanicien_nom && <><dt>Mécanicien</dt><dd>{o.mecanicien_nom}</dd></>}
        {o.diagnostic && <><dt>Diagnostic</dt><dd>{o.diagnostic}</dd></>}
        {(o.compteur_heures || o.compteur_km) && <><dt>Compteur relevé</dt><dd>{[o.compteur_heures && `${nombre(o.compteur_heures)} h`, o.compteur_km && `${nombre(o.compteur_km)} km`].filter(Boolean).join(' · ')}</dd></>}
        {o.demarre_le && <><dt>Travaux démarrés</dt><dd>le {dateHeureFr(o.demarre_le)}</dd></>}
        {o.travaux && <><dt>Travaux réalisés</dt><dd style={{ whiteSpace: 'pre-line' }}>{o.travaux}{o.termine_le && ` (terminés le ${dateHeureFr(o.termine_le)})`}</dd></>}
        {o.cloture_le && <><dt>Clôture</dt><dd>{o.cloture_par_nom}, le {dateHeureFr(o.cloture_le)}</dd></>}
        {o.motif_annulation && <><dt>Annulation</dt><dd>{o.motif_annulation}</dd></>}
      </dl>

      <h3>Pièces sorties du stock</h3>
      {o.pieces.length === 0 && <p className="aide">Aucune pièce sortie pour cet ordre.</p>}
      {o.pieces.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Date</th><th>Bon de sortie</th><th>Article</th><th className="nombre">Quantité</th>{o.couts && <><th className="nombre">Prix unitaire</th><th className="nombre">Montant</th></>}</tr></thead>
            <tbody>
              {o.pieces.map((p, i) => (
                <tr key={i}><td>{dateFr(p.date)}</td><td><a href={`#/stock/sorties/${p.bon}`}>{p.bon_numero}</a></td><td>{p.designation}<br /><span className="aide">{p.code}</span></td><td className="nombre">{nombre(p.quantite)} {p.unite}</td>{o.couts && <><td className="nombre">{p.prix_unitaire ? montant(p.prix_unitaire) : 'inconnu'}</td><td className="nombre">{p.montant ? montant(p.montant) : ''}</td></>}</tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {ouvert && peutDemanderPieces && <div className="actions"><a className="bouton secondaire" href={`#/stock/demandes/nouvelle?or=${encodeURIComponent(o.numero)}&materiel=${encodeURIComponent(o.materiel_nom)}`}>Demander des pièces au magasin</a></div>}

      <h3>Temps passé</h3>
      {o.temps.length === 0 && <p className="aide">Aucune heure saisie pour cet ordre.</p>}
      {o.temps.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Date</th><th>Mécanicien</th><th className="nombre">Heures</th>{o.couts && <th className="nombre">Montant</th>}<th></th></tr></thead>
            <tbody>
              {o.temps.map((x) => (
                <tr key={x.id}>
                  <td>{dateFr(x.date)}</td><td>{x.mecanicien_nom}{x.commentaire && <><br /><span className="aide">{x.commentaire}</span></>}</td>
                  <td className="nombre">{nombre(x.heures)} h</td>{o.couts && <td className="nombre">{x.montant ? montant(x.montant) : ''}</td>}
                  <td>{x.peut_retirer && <button className="lien" disabled={enCours} onClick={() => agir('retirer_temps', { temps: x.id })}>Retirer</button>}</td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr><th colSpan={2}>Total</th><th className="nombre">{nombre(o.temps.reduce((n, x) => n + Number(x.heures), 0))} h</th>{o.couts && <th className="nombre">{montant(o.couts.main_oeuvre)}</th>}<th></th></tr></tfoot>
          </table>
        </div>
      )}
      {o.peut_saisir_temps && (
        <form className="grille" onSubmit={(e) => { e.preventDefault(); agir('saisir_temps', t) }}>
          <label>Date
            <input type="date" required max={aujourdhui()} value={t.date} onChange={(e) => setT({ ...t, date: e.target.value })} />
          </label>
          <label>Heures
            <input type="number" required min="0.25" max="24" step="0.25" value={t.heures} onChange={(e) => setT({ ...t, heures: e.target.value })} />
          </label>
          {o.peut_piloter && (
            <label>Mécanicien
              <select value={t.mecanicien} onChange={(e) => setT({ ...t, mecanicien: e.target.value })}>
                <option value="">Moi</option>
                {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
              </select>
            </label>
          )}
          <label>Travail fait (facultatif)
            <input maxLength={200} value={t.commentaire} onChange={(e) => setT({ ...t, commentaire: e.target.value })} />
          </label>
          <div className="actions"><button className="secondaire" disabled={enCours}>Ajouter ces heures</button></div>
        </form>
      )}

      {o.couts && (
        <>
          <h3>Coût de l'ordre</h3>
          <dl>
            <dt>Main-d'œuvre</dt><dd>{montant(o.couts.main_oeuvre)} pour {nombre(o.couts.heures)} h</dd>
            <dt>Pièces</dt><dd>{montant(o.couts.pieces)}</dd>
            <dt>Total</dt><dd><strong>{montant(o.couts.total)}</strong></dd>
          </dl>
          {Number(o.couts.heures_non_chiffrees) > 0 && <p className="aide">{nombre(o.couts.heures_non_chiffrees)} h ne sont pas chiffrées : le taux horaire de l'atelier n'était pas renseigné dans l'administration au moment de la saisie.</p>}
          {o.couts.pieces_sans_prix > 0 && <p className="aide">{o.couts.pieces_sans_prix} ligne(s) de pièces sans prix connu ne sont pas comptées.</p>}
        </>
      )}

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {o.peut_piloter && ouvert && (
        <fieldset>
          <legend>Affectation</legend>
          <div className="grille">
            <label>Mécanicien
              <select value={s.mecanicien} onChange={(e) => setS({ ...s, mecanicien: e.target.value })}>
                <option value="">Non affecté</option>
                {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
              </select>
            </label>
          </div>
          <div className="actions"><button className="secondaire" disabled={enCours} onClick={() => agir('affecter', { mecanicien: s.mecanicien })}>Enregistrer l'affectation</button></div>
        </fieldset>
      )}

      {o.peut_travailler && o.statut === 'OUVERT' && (
        <fieldset>
          <legend>Démarrer les travaux</legend>
          <label>Diagnostic (facultatif)
            <textarea value={s.diagnostic} onChange={(e) => setS({ ...s, diagnostic: e.target.value })} />
          </label>
          {compteurs}
          <div className="actions"><button disabled={enCours} onClick={() => agir('demarrer', s)}>Démarrer les travaux</button></div>
        </fieldset>
      )}

      {o.peut_travailler && o.statut === 'EN_COURS' && (
        <fieldset>
          <legend>Terminer les travaux</legend>
          <label>Travaux réalisés
            <textarea value={s.travaux} onChange={(e) => setS({ ...s, travaux: e.target.value })} />
          </label>
          {compteurs}
          <div className="actions"><button disabled={enCours} onClick={() => agir('terminer', s)}>Déclarer les travaux terminés</button></div>
        </fieldset>
      )}

      {o.peut_piloter && o.statut !== 'ANNULE' && (
        <fieldset>
          <legend>{o.statut === 'TERMINE' ? 'Clôture' : o.statut === 'CLOTURE' ? 'Rouvrir' : 'Annuler'}</legend>
          <label>{o.statut === 'TERMINE' ? 'Motif (pour rouvrir seulement)' : 'Motif'}
            <textarea value={s.commentaire} onChange={(e) => setS({ ...s, commentaire: e.target.value })} />
          </label>
          <div className="actions">
            {o.statut === 'TERMINE' && <button disabled={enCours} onClick={() => agir('cloturer')}>Clôturer l'ordre</button>}
            {(o.statut === 'TERMINE' || o.statut === 'CLOTURE') && <button className="secondaire" disabled={enCours} onClick={() => agir('rouvrir', { commentaire: s.commentaire })}>Rouvrir</button>}
            {ouvert && <button className="danger" disabled={enCours} onClick={() => agir('annuler', { commentaire: s.commentaire })}>Annuler l'ordre</button>}
          </div>
        </fieldset>
      )}

      <PiecesJointes modele="technique.ordrereparation" objet={id} aide="Joignez ici des photos de la panne ou un rapport." />
    </div>
  )
}
