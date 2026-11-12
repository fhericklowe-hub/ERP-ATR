import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { montant } from '../achats/commandes'
import { dateFr } from '../achats/types'
import { type Bien, type Echeance, RECURRENCES, TYPES_ECHEANCE } from './types'

type Saisie = Pick<Echeance, 'type' | 'libelle' | 'date_echeance' | 'rappel_jours' | 'recurrence_mois' | 'bien' | 'montant_prevu'> & { id?: number }
const vide = (): Saisie => ({ type: '', libelle: '', date_echeance: '', rappel_jours: 30, recurrence_mois: 12, bien: null, montant_prevu: null })

const VUES = [['ALERTE', 'À traiter maintenant'], ['A_FAIRE', 'Toutes celles à faire'], ['FAITE', 'Faites'], ['ANNULEE', 'Annulées']]

function delai(e: Echeance) {
  if (e.situation === 'FAITE') return `Faite le ${dateFr(e.faite_le ?? '')}`
  if (e.situation === 'ANNULEE') return 'Annulée'
  const j = e.jours_restants
  if (j < 0) return `En retard de ${-j} jour${j < -1 ? 's' : ''}`
  return j === 0 ? "Aujourd'hui" : `Dans ${j} jour${j > 1 ? 's' : ''}`
}

/** Échéances à ne pas manquer : assurances, visites techniques, taxes, contrôles, fins de contrat. */
export default function Echeances() {
  const [liste, setListe] = useState<Echeance[] | null>(null)
  const [biens, setBiens] = useState<Bien[]>([])
  const [vue, setVue] = useState('ALERTE')
  const [type, setType] = useState('')
  const [s, setS] = useState<Saisie | null>(null)
  const [aFaire, setAFaire] = useState<Echeance | null>(null)
  const [fait, setFait] = useState({ faite_le: '', montant: '', commentaire: '', prochaine: '' })
  const [erreur, setErreur] = useState('')
  const [message, setMessage] = useState('')

  const charger = useCallback(() => {
    const q = new URLSearchParams({ page_size: '200' })
    if (vue === 'ALERTE') q.set('situation', 'ALERTE')
    else q.set('statut', vue)
    if (vue === 'FAITE' || vue === 'ANNULEE') q.set('ordering', '-date_echeance')
    if (type) q.set('type', type)
    api<Page<Echeance>>(`/moyens/echeances/?${q}`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [vue, type])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Bien>>('/moyens/biens/?page_size=200').then((p) => setBiens(p.results.filter((b) => b.etat !== 'REFORME'))).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!s) return
    setErreur('')
    try {
      const { id, ...corps } = s
      await api<Echeance>(id ? `/moyens/echeances/${id}/` : '/moyens/echeances/', {
        method: id ? 'PATCH' : 'POST', body: JSON.stringify({ ...corps, montant_prevu: corps.montant_prevu || null }),
      })
      setS(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  async function agir(action: 'faire' | 'annuler') {
    if (!aFaire) return
    setErreur('')
    try {
      const r = await api<Echeance & { suivante?: Echeance | null }>(`/moyens/echeances/${aFaire.id}/${action}/`, { method: 'POST', body: JSON.stringify(fait) })
      setMessage(action === 'annuler' ? 'Échéance annulée.' : r.suivante ? `Échéance faite. La prochaine est fixée au ${dateFr(r.suivante.date_echeance)}.` : 'Échéance faite.')
      setAFaire(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setS((x) => (x ? { ...x, [k]: v } : x))

  if (s) {
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <h2>{s.id ? "Modifier l'échéance" : 'Nouvelle échéance'}</h2>
        <fieldset>
          <div className="grille">
            <label>Type
              <select required value={s.type} onChange={(e) => champ('type', e.target.value)}>
                <option value="">Choisir…</option>
                {s.type === 'FIN_CONTRAT' && <option value="FIN_CONTRAT">Fin de contrat</option>}
                {TYPES_ECHEANCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Libellé
              <input required value={s.libelle} placeholder="Exemple : visite technique du pick-up" onChange={(e) => champ('libelle', e.target.value)} />
            </label>
            <label>Date d'échéance
              <input type="date" required value={s.date_echeance} onChange={(e) => champ('date_echeance', e.target.value)} />
            </label>
            <label>Prévenir combien de jours avant
              <input type="number" min="0" step="1" value={s.rappel_jours} onChange={(e) => champ('rappel_jours', Number(e.target.value))} />
            </label>
            <label>Répétition
              <select value={s.recurrence_mois} onChange={(e) => champ('recurrence_mois', Number(e.target.value))}>
                {RECURRENCES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Bien concerné (facultatif)
              <select value={s.bien ?? ''} onChange={(e) => champ('bien', e.target.value ? Number(e.target.value) : null)}>
                <option value="">Aucun</option>
                {biens.map((b) => <option key={b.id} value={b.id}>{b.numero} · {b.designation}{b.immatriculation && ` · ${b.immatriculation}`}</option>)}
              </select>
            </label>
            <label>Montant prévu (XOF, facultatif)
              <input type="number" min="0" step="1" value={s.montant_prevu ?? ''} onChange={(e) => champ('montant_prevu', e.target.value)} />
            </label>
          </div>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button>Enregistrer</button>
          <button type="button" className="secondaire" onClick={() => { setS(null); setErreur('') }}>Annuler</button>
        </div>
      </form>
    )
  }

  if (aFaire) {
    return (
      <div className="fiche">
        <h2>{aFaire.libelle}</h2>
        <p className="statut">Échéance du {dateFr(aFaire.date_echeance)} · {delai(aFaire)}</p>
        <fieldset>
          <legend>C'est fait</legend>
          <div className="grille">
            <label>Fait le
              <input type="date" value={fait.faite_le} onChange={(e) => setFait({ ...fait, faite_le: e.target.value })} />
            </label>
            <label>Montant payé (XOF, facultatif)
              <input type="number" min="0" step="1" value={fait.montant} onChange={(e) => setFait({ ...fait, montant: e.target.value })} />
            </label>
            <label>Prochaine échéance
              <input type="date" value={fait.prochaine} onChange={(e) => setFait({ ...fait, prochaine: e.target.value })} />
            </label>
          </div>
          <p className="aide">
            {aFaire.recurrence_mois
              ? `Sans date, la prochaine échéance est créée ${aFaire.recurrence_mois} mois après celle-ci.`
              : 'Sans date, aucune nouvelle échéance n\'est créée.'}
          </p>
          <label>Commentaire (obligatoire pour annuler)
            <textarea value={fait.commentaire} onChange={(e) => setFait({ ...fait, commentaire: e.target.value })} />
          </label>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button onClick={() => agir('faire')}>Marquer comme faite</button>
          <button className="danger" onClick={() => agir('annuler')}>Annuler l'échéance</button>
          <button className="secondaire" onClick={() => { setAFaire(null); setErreur('') }}>Retour</button>
        </div>
      </div>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Échéances</h2>
        <div className="actions">
          <a className="bouton secondaire" href="#/contrats">Contrats</a>
          <button onClick={() => setS(vide())}>Nouvelle échéance</button>
        </div>
      </div>
      <div className="grille filtres">
        <label>Afficher
          <select value={vue} onChange={(e) => setVue(e.target.value)}>
            {VUES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>Type
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="">Tous</option>
            <option value="FIN_CONTRAT">Fin de contrat</option>
            {TYPES_ECHEANCE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {message && <p className="aide" role="status">{message}</p>}
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p>{vue === 'ALERTE' ? 'Rien à traiter pour le moment.' : 'Aucune échéance.'}</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Date</th><th>Échéance</th><th>Délai</th><th className="nombre">Montant</th><th></th></tr></thead>
            <tbody>
              {liste.map((e) => (
                <tr key={e.id}>
                  <td>{dateFr(e.date_echeance)}</td>
                  <td>{e.libelle}<br /><span className="aide">{[e.type_libelle, e.bien_nom, e.contrat_numero, e.recurrence_mois ? `tous les ${e.recurrence_mois} mois` : ''].filter(Boolean).join(' · ')}</span></td>
                  <td><span className={`pastille ${e.situation === 'RETARD' ? 'u1' : e.situation === 'PROCHE' ? 'partielle' : e.situation === 'FAITE' ? 'complete' : ''}`}>{delai(e)}</span></td>
                  <td className="nombre">{e.montant_reel ?? e.montant_prevu ? montant(e.montant_reel ?? e.montant_prevu ?? 0) : ''}</td>
                  <td>
                    {e.statut === 'A_FAIRE' && (
                      <div className="actions">
                        <button onClick={() => { setAFaire(e); setFait({ faite_le: '', montant: e.montant_prevu ?? '', commentaire: '', prochaine: '' }); setMessage('') }}>Traiter</button>
                        <button className="secondaire" onClick={() => setS({ ...e })}>Modifier</button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
