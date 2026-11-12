import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site, type Tiers } from '../api'
import { montant } from '../achats/commandes'
import PiecesJointes from '../PiecesJointes'
import { dateFr } from '../achats/types'
import { type Bien, type Contrat, PERIODICITES, TYPES_CONTRAT } from './types'

type Saisie = Pick<Contrat, 'type' | 'objet' | 'prestataire' | 'reference' | 'site' | 'bien' | 'date_debut' | 'date_fin'
  | 'tacite_reconduction' | 'preavis_jours' | 'montant' | 'periodicite' | 'statut' | 'observations'> & { id?: number; numero?: string }

const vide = (): Saisie => ({
  type: '', objet: '', prestataire: '', reference: '', site: null, bien: null, date_debut: '', date_fin: null,
  tacite_reconduction: false, preavis_jours: 0, montant: null, periodicite: 'A', statut: 'ACTIF', observations: '',
})

/** Contrats des moyens généraux : assurances, baux, maintenance, gardiennage, abonnements. */
export default function Contrats() {
  const [contrats, setContrats] = useState<Contrat[] | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [tiers, setTiers] = useState<Tiers[]>([])
  const [biens, setBiens] = useState<Bien[]>([])
  const [filtre, setFiltre] = useState({ type: '', statut: 'ACTIF', search: '' })
  const [c, setC] = useState<Saisie | null>(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api<Page<Contrat>>(`/moyens/contrats/?${new URLSearchParams(filtre)}&page_size=200`).then((p) => setContrats(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Tiers>>('/tiers/?est_fournisseur=true&actif=true&page_size=200').then((p) => setTiers(p.results)).catch(() => undefined)
    api<Page<Bien>>('/moyens/biens/?page_size=200').then((p) => setBiens(p.results.filter((b) => b.etat !== 'REFORME'))).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!c) return
    setErreur('')
    try {
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      const { id, numero, ...corps } = c
      await api<Contrat>(id ? `/moyens/contrats/${id}/` : '/moyens/contrats/', {
        method: id ? 'PATCH' : 'POST',
        body: JSON.stringify({ ...corps, date_fin: corps.date_fin || null, montant: corps.montant || null }),
      })
      setC(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setC((x) => (x ? { ...x, [k]: v } : x))

  if (c) {
    return (
      <div className="fiche">
      <form className="fiche" onSubmit={enregistrer}>
        <h2>{c.id ? `Contrat ${c.numero}` : 'Nouveau contrat'}</h2>
        <fieldset>
          <legend>Le contrat</legend>
          <div className="grille">
            <label>Type
              <select required value={c.type} onChange={(e) => champ('type', e.target.value)}>
                <option value="">Choisir…</option>
                {TYPES_CONTRAT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Objet
              <input required value={c.objet} placeholder="Exemple : assurance flotte automobile" onChange={(e) => champ('objet', e.target.value)} />
            </label>
            <label>Prestataire ou bailleur
              <select required value={c.prestataire} onChange={(e) => champ('prestataire', Number(e.target.value))}>
                <option value="">Choisir…</option>
                {tiers.map((t) => <option key={t.id} value={t.id}>{t.raison_sociale}</option>)}
              </select>
            </label>
            <label>Référence ou n° de police
              <input value={c.reference} onChange={(e) => champ('reference', e.target.value)} />
            </label>
            <label>Site
              <select value={c.site ?? ''} onChange={(e) => champ('site', e.target.value ? Number(e.target.value) : null)}>
                <option value="">Tous les sites</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
              </select>
            </label>
            <label>Bien concerné (facultatif)
              <select value={c.bien ?? ''} onChange={(e) => champ('bien', e.target.value ? Number(e.target.value) : null)}>
                <option value="">Aucun</option>
                {biens.map((b) => <option key={b.id} value={b.id}>{b.numero} · {b.designation}</option>)}
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>Durée et montant</legend>
          <div className="grille">
            <label>Date de début
              <input type="date" required value={c.date_debut} onChange={(e) => champ('date_debut', e.target.value)} />
            </label>
            <label>Date de fin
              <input type="date" value={c.date_fin ?? ''} onChange={(e) => champ('date_fin', e.target.value)} />
            </label>
            <label>Préavis de résiliation (jours)
              <input type="number" min="0" step="1" value={c.preavis_jours} onChange={(e) => champ('preavis_jours', Number(e.target.value))} />
            </label>
            <label>Montant (XOF)
              <input type="number" min="0" step="1" value={c.montant ?? ''} onChange={(e) => champ('montant', e.target.value)} />
            </label>
            <label>Périodicité du montant
              <select value={c.periodicite} onChange={(e) => champ('periodicite', e.target.value)}>
                {PERIODICITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {c.id && (
              <label>État
                <select value={c.statut} onChange={(e) => champ('statut', e.target.value)}>
                  <option value="ACTIF">En cours</option>
                  <option value="RESILIE">Résilié ou terminé</option>
                </select>
              </label>
            )}
          </div>
          <label className="case">
            <input type="checkbox" checked={c.tacite_reconduction} onChange={(e) => champ('tacite_reconduction', e.target.checked)} />
            Le contrat se reconduit tout seul (tacite reconduction)
          </label>
          <p className="aide">Avec une date de fin, une échéance est créée à la date limite du préavis pour penser à renouveler ou résilier.</p>
          <label>Observations<textarea value={c.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button>Enregistrer</button>
          <button type="button" className="secondaire" onClick={() => { setC(null); setErreur('') }}>{c.id ? 'Retour' : 'Annuler'}</button>
        </div>
      </form>
      {c.id && <PiecesJointes modele="moyens.contrat" objet={c.id} aide="Joignez ici le contrat signé, l'attestation ou les avenants." />}
      </div>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Contrats</h2>
        <div className="actions">
          <a className="bouton secondaire" href="#/echeances">Échéances</a>
          <button onClick={() => setC(vide())}>Nouveau contrat</button>
        </div>
      </div>
      <div className="grille filtres large">
        <label>Recherche
          <input value={filtre.search} placeholder="N°, objet, prestataire…" onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} />
        </label>
        <label>Type
          <select value={filtre.type} onChange={(e) => setFiltre({ ...filtre, type: e.target.value })}>
            <option value="">Tous</option>
            {TYPES_CONTRAT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>État
          <select value={filtre.statut} onChange={(e) => setFiltre({ ...filtre, statut: e.target.value })}>
            <option value="ACTIF">En cours</option>
            <option value="RESILIE">Résiliés ou terminés</option>
            <option value="">Tous</option>
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!contrats && !erreur && <p>Chargement…</p>}
      {contrats?.length === 0 && <p>Aucun contrat.</p>}
      {contrats && contrats.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Objet</th><th>Prestataire</th><th>Période</th><th className="nombre">Montant</th><th></th></tr></thead>
            <tbody>
              {contrats.map((x) => (
                <tr key={x.id}>
                  <td>{x.numero}</td>
                  <td>{x.objet}<br /><span className="aide">{[x.type_libelle, x.reference, x.site_nom, x.bien_nom].filter(Boolean).join(' · ')}</span></td>
                  <td>{x.prestataire_nom}</td>
                  <td>
                    {dateFr(x.date_debut)} → {x.date_fin ? dateFr(x.date_fin) : 'sans fin'}
                    {x.tacite_reconduction && <><br /><span className="aide">Tacite reconduction</span></>}
                    {x.statut === 'RESILIE' && <><br /><span className="pastille">Résilié ou terminé</span></>}
                  </td>
                  <td className="nombre">{x.montant ? <>{montant(x.montant)}<br /><span className="aide">{x.periodicite_libelle.toLowerCase()}</span></> : ''}</td>
                  <td><button className="secondaire" onClick={() => setC({ ...x })}>Modifier</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
