import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import { dateFr } from '../achats/types'
import { nombre } from '../stock/types'
import { type Materiel, type Plan } from './types'

type Saisie = { id?: number; materiel: string; intitule: string; consignes: string; intervalle_heures: string; intervalle_km: string
  intervalle_mois: string; dernier_le: string; dernier_heures: string; dernier_km: string; actif: boolean }
const vide = (): Saisie => ({ materiel: '', intitule: '', consignes: '', intervalle_heures: '', intervalle_km: '', intervalle_mois: '',
  dernier_le: new Date().toLocaleDateString('fr-CA'), dernier_heures: '', dernier_km: '', actif: true })
const texte = (v: string | number | null) => (v === null ? '' : String(v))
const pastille = (s: string) => (s === 'RETARD' ? 'u1' : s === 'PROCHE' ? 'partielle' : 'complete')
const ORDRE: Record<string, number> = { RETARD: 0, PROCHE: 1, A_VENIR: 2 }

/** « dans 120 h », « dépassé de 10 h » : ce qu'il reste avant chaque échéance du plan. */
function reste(p: Plan) {
  return p.restes.map(({ reste, unite }) => {
    const n = Number(reste)
    const quantite = `${nombre(Math.abs(n))} ${unite === 'j' ? (Math.abs(n) > 1 ? 'jours' : 'jour') : unite}`
    return n <= 0 ? `dépassé de ${quantite}` : `dans ${quantite}`
  }).join(' · ')
}

/** Entretien préventif : les opérations périodiques de chaque matériel, les plus urgentes en premier. */
export default function Entretien({ peutModifier, peutOuvrir }: { peutModifier: boolean; peutOuvrir: boolean }) {
  const [plans, setPlans] = useState<Plan[] | null>(null)
  const [materiels, setMateriels] = useState<Materiel[]>([])
  const [filtre, setFiltre] = useState({ search: '', vue: 'A_FAIRE' })
  const [s, setS] = useState<Saisie | null>(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    const actif = filtre.vue === 'ABANDONNES' ? 'false' : 'true'
    api<Page<Plan>>(`/technique/plans/?${new URLSearchParams({ search: filtre.search, actif })}&page_size=200`)
      .then((p) => setPlans(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre.search, filtre.vue])
  useEffect(charger, [charger])
  useEffect(() => {
    if (peutModifier) api<Page<Materiel>>('/technique/materiels/?page_size=200').then((p) => setMateriels(p.results.filter((m) => m.etat !== 'REFORME'))).catch(() => undefined)
  }, [peutModifier])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!s) return
    setErreur('')
    setEnCours(true)
    try {
      const { id, materiel, ...reste } = s
      const corps = {
        ...reste, intervalle_heures: reste.intervalle_heures || null, intervalle_km: reste.intervalle_km || null, intervalle_mois: reste.intervalle_mois || null,
        dernier_heures: reste.dernier_heures || null, dernier_km: reste.dernier_km || null,
      }
      await api<Plan>(id ? `/technique/plans/${id}/` : '/technique/plans/', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(id ? corps : { ...corps, materiel }) })
      setS(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  async function ouvrir(p: Plan) {
    setErreur('')
    setEnCours(true)
    try {
      const ordre = await api<{ id: number }>(`/technique/plans/${p.id}/ouvrir_ordre/`, { method: 'POST' })
      location.hash = `#/ordres/${ordre.id}`
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (s) {
    const m = materiels.find((x) => String(x.id) === s.materiel)
    const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setS({ ...s, [k]: v })
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <h2>{s.id ? "Modifier l'entretien" : 'Nouvel entretien périodique'}</h2>
        <fieldset>
          <legend>Opération</legend>
          <div className="grille">
            <label>Matériel
              <select required disabled={!!s.id} value={s.materiel} onChange={(e) => champ('materiel', e.target.value)}>
                <option value="">Choisir…</option>
                {materiels.map((x) => <option key={x.id} value={x.id}>{x.code} · {x.designation}</option>)}
              </select>
            </label>
            <label>Opération<input required maxLength={120} placeholder="Vidange moteur et filtres" value={s.intitule} onChange={(e) => champ('intitule', e.target.value)} /></label>
          </div>
          <label>Consignes, pièces à prévoir (facultatif)
            <textarea value={s.consignes} onChange={(e) => champ('consignes', e.target.value)} />
          </label>
        </fieldset>
        <fieldset>
          <legend>Périodicité</legend>
          <p className="aide">Remplissez une ou plusieurs cases. L'entretien est à faire dès que la première limite est atteinte.</p>
          <div className="grille">
            <label>Toutes les (heures)<input type="number" min="1" step="1" value={s.intervalle_heures} onChange={(e) => champ('intervalle_heures', e.target.value)} /></label>
            <label>Tous les (km)<input type="number" min="1" step="1" value={s.intervalle_km} onChange={(e) => champ('intervalle_km', e.target.value)} /></label>
            <label>Tous les (mois)<input type="number" min="1" step="1" value={s.intervalle_mois} onChange={(e) => champ('intervalle_mois', e.target.value)} /></label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Dernière réalisation</legend>
          <p className="aide">Sans relevé de compteur, le décompte part du compteur actuel du matériel{m && (m.compteur_heures || m.compteur_km) ? ` (${[m.compteur_heures && `${nombre(m.compteur_heures)} h`, m.compteur_km && `${nombre(m.compteur_km)} km`].filter(Boolean).join(', ')})` : ''}.</p>
          <div className="grille">
            <label>Date<input type="date" required max={new Date().toLocaleDateString('fr-CA')} value={s.dernier_le} onChange={(e) => champ('dernier_le', e.target.value)} /></label>
            {s.intervalle_heures && <label>Compteur ce jour-là (heures)<input type="number" min="0" step="0.1" value={s.dernier_heures} onChange={(e) => champ('dernier_heures', e.target.value)} /></label>}
            {s.intervalle_km && <label>Compteur ce jour-là (km)<input type="number" min="0" step="1" value={s.dernier_km} onChange={(e) => champ('dernier_km', e.target.value)} /></label>}
          </div>
          {s.id && (
            <label className="case">
              <input type="checkbox" checked={s.actif} onChange={(e) => champ('actif', e.target.checked)} />
              Entretien suivi (décochez pour l'abandonner)
            </label>
          )}
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button disabled={enCours}>Enregistrer</button>
          <button type="button" className="secondaire" onClick={() => { setS(null); setErreur('') }}>Annuler</button>
        </div>
      </form>
    )
  }

  const visibles = (plans ?? [])
    .filter((p) => filtre.vue !== 'A_FAIRE' || p.situation !== 'A_VENIR')
    .sort((x, y) => ORDRE[x.situation] - ORDRE[y.situation] || x.materiel_nom.localeCompare(y.materiel_nom))
  return (
    <div>
      <div className="barre">
        <h2>Entretien préventif</h2>
        {peutModifier && <button onClick={() => { setErreur(''); setS(vide()) }}>Nouvel entretien périodique</button>}
      </div>
      <div className="grille filtres">
        <label>Recherche<input placeholder="Opération, matériel" value={filtre.search} onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} /></label>
        <label>Afficher
          <select value={filtre.vue} onChange={(e) => setFiltre({ ...filtre, vue: e.target.value })}>
            <option value="A_FAIRE">À faire et bientôt</option>
            <option value="TOUS">Tous les entretiens suivis</option>
            <option value="ABANDONNES">Entretiens abandonnés</option>
          </select>
        </label>
      </div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {!plans && !erreur && <p>Chargement…</p>}
      {plans && visibles.length === 0 && <p className="aide">{filtre.vue === 'A_FAIRE' ? "Aucun entretien à faire pour l'instant." : 'Aucun entretien enregistré.'}</p>}
      {visibles.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>Matériel</th><th>Opération</th><th>Périodicité</th><th>Prochaine échéance</th><th>Situation</th><th></th></tr></thead>
            <tbody>
              {visibles.map((p) => (
                <tr key={p.id}>
                  <td>{p.materiel_nom}<br /><span className="aide">{[p.site_nom, p.compteur_heures && `${nombre(p.compteur_heures)} h`, p.compteur_km && `${nombre(p.compteur_km)} km`].filter(Boolean).join(' · ')}</span></td>
                  <td>{p.intitule}<br /><span className="aide">Dernière fois le {dateFr(p.dernier_le)}</span></td>
                  <td>{[p.intervalle_heures && `${nombre(p.intervalle_heures)} h`, p.intervalle_km && `${nombre(p.intervalle_km)} km`, p.intervalle_mois && `${p.intervalle_mois} mois`].filter(Boolean).join(' ou ')}</td>
                  <td>{[p.prochaines_heures && `${nombre(p.prochaines_heures)} h`, p.prochain_km && `${nombre(p.prochain_km)} km`, p.prochaine_date && dateFr(p.prochaine_date)].filter(Boolean).join(' · ')}<br /><span className="aide">{reste(p)}</span></td>
                  <td><span className={`pastille ${p.actif ? pastille(p.situation) : ''}`}>{p.actif ? p.situation_libelle : 'Abandonné'}</span></td>
                  <td>
                    <div className="actions">
                      {p.ordre_en_cours && <a href={`#/ordres/${p.ordre_en_cours.id}`}>{p.ordre_en_cours.numero}</a>}
                      {!p.ordre_en_cours && p.actif && peutOuvrir && <button className="secondaire" disabled={enCours} onClick={() => ouvrir(p)}>Ouvrir l'OR</button>}
                      {peutModifier && <button className="lien" onClick={() => { setErreur(''); setS({ id: p.id, materiel: String(p.materiel), intitule: p.intitule, consignes: p.consignes, intervalle_heures: texte(p.intervalle_heures), intervalle_km: texte(p.intervalle_km), intervalle_mois: texte(p.intervalle_mois), dernier_le: p.dernier_le, dernier_heures: texte(p.dernier_heures), dernier_km: texte(p.dernier_km), actif: p.actif }) }}>Modifier</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
