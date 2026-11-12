import { type FormEvent, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site, type Utilisateur } from '../api'
import { type Bien, CATEGORIES, type Intervention } from './types'

type Saisie = Pick<Intervention, 'service' | 'site' | 'lieu' | 'bien' | 'categorie' | 'priorite' | 'objet' | 'description'>

export default function FormulaireIntervention({ moi, id }: { moi: Utilisateur; id?: number }) {
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [biens, setBiens] = useState<Bien[]>([])
  const [d, setD] = useState<Saisie>({
    service: moi.service ?? '', site: moi.site ?? '', lieu: '', bien: null, categorie: '', priorite: 2, objet: '', description: '',
  })
  const [enPanne, setEnPanne] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([
      api<Page<Site>>('/sites/?actif=true'), api<Page<Service>>('/services/?actif=true'),
      id ? api<Intervention>(`/moyens/interventions/${id}/`) : null,
    ])
      .then(([si, se, demande]) => {
        setSites(si.results)
        setServices(se.results)
        if (demande) setD(demande)
      })
      .catch((e: Error) => setErreur(e.message))
  }, [id])

  // Les biens proposés sont ceux du site choisi.
  useEffect(() => {
    if (!d.site) return setBiens([])
    api<Page<Bien>>(`/moyens/biens/?site=${d.site}&page_size=200`).then((p) => setBiens(p.results.filter((b) => b.etat !== 'REFORME'))).catch(() => setBiens([]))
  }, [d.site])

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setD((x) => ({ ...x, [k]: v }))

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setEnCours(true)
    setErreur('')
    try {
      const { service, site, lieu, bien, categorie, priorite, objet, description } = d
      const r = await api<Intervention>(id ? `/moyens/interventions/${id}/` : '/moyens/interventions/', {
        method: id ? 'PATCH' : 'POST',
        body: JSON.stringify({ service, site, lieu, bien, categorie, priorite, objet, description, bien_en_panne: enPanne }),
      })
      location.hash = `#/interventions/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>{id ? "Modifier la demande d'intervention" : "Nouvelle demande d'intervention"}</h2>
      <fieldset>
        <legend>Le problème</legend>
        <label>Objet
          <input required value={d.objet} placeholder="Exemple : climatiseur en panne au bureau commercial" onChange={(e) => champ('objet', e.target.value)} />
        </label>
        <div className="grille">
          <label>Catégorie
            <select required value={d.categorie} onChange={(e) => champ('categorie', e.target.value)}>
              <option value="">Choisir…</option>
              {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label>Priorité
            <select value={d.priorite} onChange={(e) => champ('priorite', Number(e.target.value))}>
              <option value={1}>Urgente (sécurité ou activité bloquée)</option>
              <option value={2}>Normale</option>
              <option value={3}>Peut attendre</option>
            </select>
          </label>
        </div>
        <label>Description
          <textarea value={d.description} onChange={(e) => champ('description', e.target.value)} />
        </label>
      </fieldset>

      <fieldset>
        <legend>Où</legend>
        <div className="grille">
          <label>Service
            <select required value={d.service} onChange={(e) => champ('service', Number(e.target.value))}>
              <option value="">Choisir…</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Site
            <select required value={d.site} onChange={(e) => setD((x) => ({ ...x, site: Number(e.target.value), bien: null }))}>
              <option value="">Choisir…</option>
              {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
            </select>
          </label>
          <label>Lieu précis
            <input value={d.lieu} placeholder="Bureau, étage, atelier…" onChange={(e) => champ('lieu', e.target.value)} />
          </label>
          <label>Bien concerné (facultatif)
            <select value={d.bien ?? ''} onChange={(e) => champ('bien', e.target.value ? Number(e.target.value) : null)}>
              <option value="">Aucun ou inconnu</option>
              {biens.map((b) => <option key={b.id} value={b.id}>{b.numero} · {b.designation}</option>)}
            </select>
          </label>
        </div>
        {d.bien && !id && (
          <label className="case">
            <input type="checkbox" checked={enPanne} onChange={(e) => setEnPanne(e.target.checked)} />
            Ce bien est hors d'usage (le marquer « en panne » dans l'inventaire)
          </label>
        )}
      </fieldset>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Envoi…' : id ? 'Enregistrer' : 'Envoyer la demande'}</button>
        <a href={id ? `#/interventions/${id}` : '#/interventions'}>Annuler</a>
      </div>
    </form>
  )
}
