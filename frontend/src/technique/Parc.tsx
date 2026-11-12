import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page, type Site } from '../api'
import PiecesJointes from '../PiecesJointes'
import { ACTIVITES, ETATS_MATERIEL, type Materiel, TYPES_MATERIEL, pastilleEtat } from './types'

type Saisie = Pick<Materiel, 'code' | 'type' | 'designation' | 'marque' | 'modele' | 'numero_serie' | 'immatriculation' | 'annee' | 'capacite'
  | 'activite' | 'site' | 'emplacement' | 'etat' | 'compteur_heures' | 'compteur_km' | 'observations'> & { id?: number }
type Lieu = { id: number; nom: string; type: string }

const vide = (): Saisie => ({
  code: '', type: '', designation: '', marque: '', modele: '', numero_serie: '', immatriculation: '', annee: null, capacite: '', activite: '',
  site: '', emplacement: null, etat: 'DISPONIBLE', compteur_heures: null, compteur_km: null, observations: '',
})

/** Parc de matériels : engins de manutention et de levage, camions, véhicules. */
export default function Parc({ peutModifier }: { peutModifier: boolean }) {
  const [liste, setListe] = useState<Materiel[] | null>(null)
  const [sites, setSites] = useState<Site[]>([])
  const [lieux, setLieux] = useState<Lieu[]>([])
  const [filtre, setFiltre] = useState({ search: '', type: '', site: '', etat: '' })
  const [m, setM] = useState<Saisie | null>(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api<Page<Materiel>>(`/technique/materiels/?${new URLSearchParams(filtre)}&page_size=200`).then((p) => setListe(p.results)).catch((e: Error) => setErreur(e.message))
  }, [filtre])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Site>>('/sites/?actif=true').then((p) => setSites(p.results)).catch(() => undefined)
    api<Page<Lieu>>('/emplacements/?actif=true&page_size=200').then((p) => setLieux(p.results)).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    if (!m) return
    setErreur('')
    try {
      const { id, ...corps } = m
      await api<Materiel>(id ? `/technique/materiels/${id}/` : '/technique/materiels/', {
        method: id ? 'PATCH' : 'POST',
        body: JSON.stringify({ ...corps, annee: corps.annee || null, compteur_heures: corps.compteur_heures || null, compteur_km: corps.compteur_km || null }),
      })
      setM(null)
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }

  const champ = <K extends keyof Saisie>(k: K, v: Saisie[K]) => setM((x) => (x ? { ...x, [k]: v } : x))

  if (m) {
    return (
      <div className="fiche">
        <form className="fiche" onSubmit={enregistrer}>
          <h2>{m.id ? `Matériel ${m.code}` : 'Nouveau matériel'}</h2>
          <fieldset>
            <legend>Identification</legend>
            <div className="grille">
              <label>N° de parc<input required value={m.code} maxLength={30} onChange={(e) => champ('code', e.target.value)} /></label>
              <label>Type
                <select required value={m.type} onChange={(e) => champ('type', e.target.value)}>
                  <option value="">Choisir…</option>
                  {TYPES_MATERIEL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label>Désignation<input required value={m.designation} onChange={(e) => champ('designation', e.target.value)} /></label>
              <label>Marque<input value={m.marque} onChange={(e) => champ('marque', e.target.value)} /></label>
              <label>Modèle<input value={m.modele} onChange={(e) => champ('modele', e.target.value)} /></label>
              <label>N° de série<input value={m.numero_serie} onChange={(e) => champ('numero_serie', e.target.value)} /></label>
              <label>Immatriculation<input value={m.immatriculation} onChange={(e) => champ('immatriculation', e.target.value)} /></label>
              <label>Année<input type="number" min="1950" max="2100" value={m.annee ?? ''} onChange={(e) => champ('annee', e.target.value ? Number(e.target.value) : null)} /></label>
              <label>Capacité<input value={m.capacite} placeholder="3,5 t ; 50 t ; 12 m" onChange={(e) => champ('capacite', e.target.value)} /></label>
              <label>Activité
                <select value={m.activite} onChange={(e) => champ('activite', e.target.value)}>
                  <option value="">Non précisée</option>
                  {ACTIVITES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
            </div>
          </fieldset>
          <fieldset>
            <legend>Situation</legend>
            <div className="grille">
              <label>Site de rattachement
                <select required value={m.site} onChange={(e) => champ('site', Number(e.target.value))}>
                  <option value="">Choisir…</option>
                  {sites.map((s) => <option key={s.id} value={s.id}>{s.nom}</option>)}
                </select>
              </label>
              <label>Où il se trouve
                <select value={m.emplacement ?? ''} onChange={(e) => champ('emplacement', e.target.value ? Number(e.target.value) : null)}>
                  <option value="">Sur son site</option>
                  {lieux.map((l) => <option key={l.id} value={l.id}>{l.nom}{l.type === 'CLIENT' ? ' (client)' : ''}</option>)}
                </select>
              </label>
              <label>État
                <select value={m.etat} onChange={(e) => champ('etat', e.target.value)}>
                  {ETATS_MATERIEL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </select>
              </label>
              <label>Compteur (heures)<input type="number" min="0" step="0.1" value={m.compteur_heures ?? ''} onChange={(e) => champ('compteur_heures', e.target.value)} /></label>
              <label>Compteur (km)<input type="number" min="0" step="1" value={m.compteur_km ?? ''} onChange={(e) => champ('compteur_km', e.target.value ? Number(e.target.value) : null)} /></label>
            </div>
            <p className="aide">Un ordre de réparation ouvert passe le matériel « en panne », puis « en réparation » quand les travaux démarrent.</p>
            <label>Observations<textarea value={m.observations} onChange={(e) => champ('observations', e.target.value)} /></label>
          </fieldset>
          {erreur && <p className="erreur" role="alert">{erreur}</p>}
          <div className="actions">
            <button>Enregistrer</button>
            <button type="button" className="secondaire" onClick={() => { setM(null); setErreur('') }}>{m.id ? 'Retour' : 'Annuler'}</button>
          </div>
        </form>
        {m.id && <PiecesJointes modele="technique.materiel" objet={m.id} aide="Joignez ici la carte grise, l'assurance, le rapport de vérification." />}
      </div>
    )
  }

  return (
    <>
      <div className="barre">
        <h2>Parc de matériels</h2>
        <div className="actions">
          <a className="bouton secondaire" href="#/ordres">Ordres de réparation</a>
          {peutModifier && <button onClick={() => setM(vide())}>Nouveau matériel</button>}
        </div>
      </div>
      <div className="grille filtres large">
        <label>Recherche
          <input value={filtre.search} placeholder="N° de parc, désignation, immatriculation…" onChange={(e) => setFiltre({ ...filtre, search: e.target.value })} />
        </label>
        <label>Type
          <select value={filtre.type} onChange={(e) => setFiltre({ ...filtre, type: e.target.value })}>
            <option value="">Tous</option>
            {TYPES_MATERIEL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
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
            {ETATS_MATERIEL.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!liste && !erreur && <p>Chargement…</p>}
      {liste?.length === 0 && <p>Aucun matériel.</p>}
      {liste && liste.length > 0 && (
        <div className="defilant">
          <table>
            <thead><tr><th>N° de parc</th><th>Matériel</th><th>Site</th><th>Compteur</th><th>État</th><th></th></tr></thead>
            <tbody>
              {liste.map((x) => (
                <tr key={x.id}>
                  <td>{x.code}</td>
                  <td>{x.designation}<br /><span className="aide">{[x.type_libelle, x.marque, x.modele, x.immatriculation, x.capacite].filter(Boolean).join(' · ')}</span></td>
                  <td>{x.site_nom}{x.emplacement_nom && x.emplacement_nom !== x.site_nom && <><br /><span className="aide">chez {x.emplacement_nom}</span></>}</td>
                  <td>{[x.compteur_heures && `${Number(x.compteur_heures).toLocaleString('fr-FR')} h`, x.compteur_km && `${x.compteur_km.toLocaleString('fr-FR')} km`].filter(Boolean).join(' · ')}</td>
                  <td>
                    <span className={`pastille ${pastilleEtat(x.etat)}`}>{x.etat_libelle}</span>
                    {x.ordres_ouverts > 0 && <><br /><a className="aide" href={`#/ordres?materiel=${x.id}`}>{x.ordres_ouverts} OR ouvert(s)</a></>}
                  </td>
                  <td>
                    <div className="actions">
                      <a className="bouton secondaire" href={`#/ordres/nouveau?materiel=${x.id}`}>Ouvrir un OR</a>
                      {peutModifier && <button className="secondaire" onClick={() => setM({ ...x })}>Modifier</button>}
                    </div>
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
