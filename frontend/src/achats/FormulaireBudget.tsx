import { type FormEvent, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site, type Tiers, type Utilisateur } from '../api'
import { type DemandeBudget, type LigneBudgetaire, NATURES, type Projet, TYPES } from './budget'
import { montant } from './commandes'

type Saisie = Pick<DemandeBudget, 'type' | 'fast_track' | 'service' | 'site' | 'activite' | 'activite_autre' | 'projet' | 'intitule'
  | 'description' | 'prevu_budget' | 'ligne_budgetaire' | 'motif_hors_budget' | 'nature' | 'motif_investissement' | 'numero_contrat'
  | 'client' | 'loyer_mensuel' | 'ancien_numero'>

/** Partie du demandeur : création, ou correction d'un brouillon (id). */
export default function FormulaireBudget({ moi, id }: { moi: Utilisateur; id?: number }) {
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [projets, setProjets] = useState<Projet[]>([])
  const [lignes, setLignes] = useState<LigneBudgetaire[]>([])
  const [clients, setClients] = useState<Tiers[]>([])
  const [d, setD] = useState<Saisie>({
    type: 'FG', fast_track: false, service: moi.service ?? '', site: moi.site ?? '', activite: '', activite_autre: '', projet: null,
    intitule: '', description: '', prevu_budget: true, ligne_budgetaire: null, motif_hors_budget: '', nature: '',
    motif_investissement: '', numero_contrat: '', client: null, loyer_mensuel: null, ancien_numero: '',
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([
      api<Page<Site>>('/sites/?actif=true'),
      api<Page<Service>>('/services/?actif=true'),
      api<Projet[]>('/projets/?actif=true'),
      api<LigneBudgetaire[]>(`/achats/lignes-budgetaires/?actif=true&exercice=${new Date().getFullYear()}`),
      api<Page<Tiers>>('/tiers/?est_client=true&actif=true').catch(() => ({ results: [] as Tiers[] })),
      id ? api<DemandeBudget>(`/achats/demandes-budget/${id}/`) : null,
    ])
      .then(([si, se, pr, li, cl, demande]) => {
        setSites(si.results)
        setServices(se.results)
        setProjets(pr)
        setLignes(li)
        setClients(cl.results)
        if (demande) setD(demande)
      })
      .catch((e: Error) => setErreur(e.message))
  }, [id])

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setD((x) => ({ ...x, [k]: v }))
  const invest = d.type !== 'FG'
  const projet = projets.find((p) => p.id === d.projet)
  const lignesService = lignes.filter((l) => l.service === d.service)

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setEnCours(true)
    setErreur('')
    try {
      const { type, ...reste } = d
      const corps = {
        ...reste, ...(id ? {} : { type }),
        ligne_budgetaire: d.prevu_budget ? d.ligne_budgetaire : null,
        nature: invest ? d.nature : '', motif_investissement: d.type === 'DI_P' ? d.motif_investissement : '',
        loyer_mensuel: d.loyer_mensuel || null,
      }
      const r = await api<DemandeBudget>(id ? `/achats/demandes-budget/${id}/` : '/achats/demandes-budget/', {
        method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps),
      })
      location.hash = `#/budget/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>{id ? 'Modifier la demande' : 'Nouvelle demande liée au budget'}</h2>

      <fieldset>
        <legend>Demande</legend>
        <div className="grille">
          <label>Type de demande
            <select value={d.type} disabled={!!id} onChange={(e) => setD((x) => ({ ...x, type: e.target.value as Saisie['type'], nature: '' }))}>
              {TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label>Service demandeur
            <select required value={d.service} onChange={(e) => setD((x) => ({ ...x, service: Number(e.target.value), ligne_budgetaire: null }))}>
              <option value="">Choisir…</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Site
            <select required value={d.site} onChange={(e) => champ('site', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Activité
            <select value={d.activite} onChange={(e) => champ('activite', e.target.value)}>
              <option value="">Non précisée</option>
              <option value="MANUTENTION">Manutention</option>
              <option value="LEVAGE">Levage</option>
              <option value="TRANSPORT">Transport</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>
          {d.activite === 'AUTRE' && (
            <label>Préciser l'activité
              <input value={d.activite_autre} onChange={(e) => champ('activite_autre', e.target.value)} />
            </label>
          )}
          <label>Projet / client
            <select value={d.projet ?? ''} onChange={(e) => champ('projet', e.target.value ? Number(e.target.value) : null)}>
              <option value="">Aucun</option>
              {projets.map((p) => <option key={p.id} value={p.id}>{p.activite ? `${p.activite} · ` : ''}{p.nom}</option>)}
            </select>
          </label>
          <label>Code analytique
            <input value={projet?.code_analytique ?? ''} disabled />
          </label>
        </div>
        <label>Intitulé
          <input required value={d.intitule} onChange={(e) => champ('intitule', e.target.value)} />
        </label>
        <label>Description de l'achat
          <textarea value={d.description} onChange={(e) => champ('description', e.target.value)} />
        </label>
        <label className="case">
          <input type="checkbox" checked={d.fast_track} onChange={(e) => champ('fast_track', e.target.checked)} />
          Fast-Track
        </label>
      </fieldset>

      {invest && (
        <fieldset>
          <legend>Investissement</legend>
          <div className="grille">
            <label>Nature
              <select required value={d.nature} onChange={(e) => champ('nature', e.target.value)}>
                <option value="">Choisir…</option>
                {NATURES[d.type].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            {d.type === 'DI_P' && (
              <>
                <label>Motif
                  <select required value={d.motif_investissement} onChange={(e) => champ('motif_investissement', e.target.value)}>
                    <option value="">Choisir…</option>
                    <option value="DEVELOPPEMENT">Développement</option>
                    <option value="RENOUVELLEMENT">Renouvellement</option>
                  </select>
                </label>
                <label>N° de contrat
                  <input value={d.numero_contrat} onChange={(e) => champ('numero_contrat', e.target.value)} />
                </label>
                <label>Client
                  <select value={d.client ?? ''} onChange={(e) => champ('client', e.target.value ? Number(e.target.value) : null)}>
                    <option value="">Aucun</option>
                    {clients.map((c) => <option key={c.id} value={c.id}>{c.raison_sociale}</option>)}
                  </select>
                </label>
                <label>Loyer mensuel (XOF)
                  <input type="number" min="0" step="1" value={d.loyer_mensuel ?? ''} onChange={(e) => champ('loyer_mensuel', e.target.value)} />
                </label>
              </>
            )}
          </div>
        </fieldset>
      )}

      <fieldset>
        <legend>Budget</legend>
        <label className="case">
          <input type="checkbox" checked={d.prevu_budget} onChange={(e) => champ('prevu_budget', e.target.checked)} />
          Cet achat est prévu au budget
        </label>
        {d.prevu_budget ? (
          <label>Ligne budgétaire (le contrôle de gestion la confirmera)
            <select value={d.ligne_budgetaire ?? ''} onChange={(e) => champ('ligne_budgetaire', e.target.value ? Number(e.target.value) : null)}>
              <option value="">Je ne sais pas</option>
              {lignesService.map((l) => <option key={l.id} value={l.id}>{l.intitule} · disponible {montant(l.disponible)}</option>)}
            </select>
          </label>
        ) : (
          <label>Motif du hors budget
            <textarea required value={d.motif_hors_budget} onChange={(e) => champ('motif_hors_budget', e.target.value)} />
          </label>
        )}
        {(invest || !d.prevu_budget) && (
          <p className="aide">La direction générale donnera son accord avant la consultation des fournisseurs.</p>
        )}
      </fieldset>

      <label>N° dans l'ancien logiciel (facultatif)
        <input value={d.ancien_numero} onChange={(e) => champ('ancien_numero', e.target.value)} />
      </label>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer le brouillon'}</button>
        <a href={id ? `#/budget/${id}` : '#/budget'}>Annuler</a>
      </div>
    </form>
  )
}
