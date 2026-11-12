import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site } from '../api'
import { type Bien, CATEGORIES_BIEN, ETATS_BIEN } from './types'

type Saisie = Pick<Bien, 'categorie' | 'designation' | 'marque' | 'modele' | 'numero_serie' | 'immatriculation' | 'site' | 'emplacement'
  | 'service' | 'date_acquisition' | 'valeur_acquisition' | 'etat' | 'observations'> & { id?: number }

const vide = (): Saisie => ({
  categorie: '', designation: '', marque: '', modele: '', numero_serie: '', immatriculation: '', site: '', emplacement: '',
  service: null, date_acquisition: null, valeur_acquisition: null, etat: 'EN_SERVICE', observations: '',
})

/** Inventaire des biens : liste filtrable, et fiche de saisie pour le gestionnaire. */
export default function Biens({ peutModifier }: { peutModifier: boolean }) {
  const [biens, setBiens] = useState<Bien[] | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [filtre, setFiltre] = useState({ categorie: '', site: '', etat: '', search: '' })
  const [b, setB] = useState<Saisie | null>(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api<Page<Bien>>(`/moyens/biens/?${new URLSearchParams(filtre)}&page_size=200`).then((p) => setBiens(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Service>>('/services/?actif=true').then((p) => setServices(p.results)).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!b) return
    setErreur('')
    try {
      const { id, ...corps } = b
      await api<Bien>(id ? `/moyens/biens/${id}/` : '/moyens/biens/', {
        method: id ? 'PATCH' : 'POST',
        body: JSON.stringify({ ...corps, date_acquisition: corps.date_acquisition || null, valeur_acquisition: corps.valeur_acquisition || null }),
      })
      setB(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setB((x) => (x ? { ...x, [k]: v } : x))

  if (b) {
    return (
      <form className="fiche" onSubmit={enregistrer}>
        <h2>{b.id ? 'Modifier le bien' : 'Nouveau bien'}</h2>
        <fieldset>
          <legend>Identification</legend>
          <div className="grille">
            <label>Catégorie
              <select required value={b.categorie} onChange={(e) => champ('categorie', e.target.value)}>
                <option value="">Choisir…</option>
                {CATEGORIES_BIEN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Désignation
              <input required value={b.designation} onChange={(e) => champ('designation', e.target.value)} />
            </label>
            <label>Marque<input value={b.marque} onChange={(e) => champ('marque', e.target.value)} /></label>
            <label>Modèle<input value={b.modele} onChange={(e) => champ('modele', e.target.value)} /></label>
            <label>N° de série<input value={b.numero_serie} onChange={(e) => champ('numero_serie', e.target.value)} /></label>
            {b.categorie === 'VEHICULE' && (
              <label>Immatriculation<input value={b.immatriculation} onChange={(e) => champ('immatriculation', e.target.value)} /></label>
            )}
          </div>
        </fieldset>
        <fieldset>
          <legend>Affectation et état</legend>
          <div className="grille">
            <label>Site
              <select required value={b.site} onChange={(e) => champ('site', Number(e.target.value))}>
                <option value="">Choisir…</option>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
              </select>
            </label>
            <label>Emplacement précis<input value={b.emplacement} onChange={(e) => champ('emplacement', e.target.value)} /></label>
            <label>Service utilisateur
              <select value={b.service ?? ''} onChange={(e) => champ('service', e.target.value ? Number(e.target.value) : null)}>
                <option value="">Aucun</option>
                {services.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
              </select>
            </label>
            <label>État
              <select value={b.etat} onChange={(e) => champ('etat', e.target.value)}>
                {ETATS_BIEN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </label>
            <label>Date d'acquisition
              <input type="date" value={b.date_acquisition ?? ''} onChange={(e) => champ('date_acquisition', e.target.value)} />
            </label>
            <label>Valeur d'acquisition (XOF)
              <input type="number" min="0" step="1" value={b.valeur_acquisition ?? ''} onChange={(e) => champ('valeur_acquisition', e.target.value)} />
            </label>
          </div>
          <label>Observations<textarea value={b.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
        </fieldset>
        {erreur && <p className="erreur" role="alert">{erreur}</p>}
        <div className="actions">
          <button>Enregistrer</button>
          <button type="button" className="secondaire" onClick={() => { setB(null); setErreur('') }}>Annuler</button>
        </div>
      </form>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Inventaire des biens</h2>
        {peutModifier && <button onClick={() => setB(vide())}>Nouveau bien</button>}
      </div>
      <div className="grille filtres large">
        <label>Recherche
          <input value={filtre.search} placeholder="N°, désignation, série…" onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} />
        </label>
        <label>Catégorie
          <select value={filtre.categorie} onChange={(e) => setFiltre({ ...filtre, categorie: e.target.value })}>
            <option value="">Toutes</option>
            {CATEGORIES_BIEN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>Site
          <select value={filtre.site} onChange={(e) => setFiltre({ ...filtre, site: e.target.value })}>
            <option value="">Tous</option>
            {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
          </select>
        </label>
        <label>État
          <select value={filtre.etat} onChange={(e) => setFiltre({ ...filtre, etat: e.target.value })}>
            <option value="">Tous</option>
            {ETATS_BIEN.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!biens && !erreur && <p>Chargement…</p>}
      {biens?.length === 0 && <p>Aucun bien.</p>}
      {biens && biens.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N°</th><th>Désignation</th><th>Catégorie</th><th>Site</th><th>Service</th><th>État</th><th></th></tr></thead>
            <tbody>
              {biens.map((x) => (
                <tr key={x.id}>
                  <td>{x.numero}</td>
                  <td>{x.designation}<br /><span className="aide">{[x.marque, x.modele, x.immatriculation || x.numero_serie].filter(Boolean).join(' · ')}</span></td>
                  <td>{x.categorie_libelle}</td>
                  <td>{x.site_nom}{x.emplacement && ` · ${x.emplacement}`}</td>
                  <td>{x.service_nom}</td>
                  <td>
                    <span className={`pastille ${x.etat === 'EN_SERVICE' ? 'complete' : x.etat === 'REFORME' ? '' : 'u1'}`}>{x.etat_libelle}</span>
                    {x.interventions_ouvertes > 0 && <><br /><span className="aide">{x.interventions_ouvertes} intervention(s) en cours</span></>}
                  </td>
                  <td>{peutModifier && <button className="secondaire" onClick={() => setB(x)}>Modifier</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
