import { type FormEvent, useEffect, useState } from 'react'
import { api, type Page, type Service, type Site, type Unite, type Utilisateur } from '../api'
import type { Demande, Ligne } from './types'

const ligneVide = (): Ligne => ({ designation: '', reference_constructeur: '', quantite: '1', unite: '', observations: '' })

type Brouillon = Omit<Demande, 'id' | 'numero' | 'demandeur' | 'statut' | 'statut_libelle' | 'demandeur_nom' | 'service_nom' | 'site_nom'
  | 'recue_le' | 'echeance_commande' | 'en_retard' | 'elements_manquants' | 'controle_stock' | 'modifiable'
  | 'peut_valider' | 'peut_traiter' | 'acheteur' | 'acheteur_nom' | 'pieces_jointes' | 'evenements' | 'date_demande' | 'ancien_numero'>

export default function Formulaire({ moi, id }: { moi: Utilisateur; id?: number }) {
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [unites, setUnites] = useState<Unite[]>([])
  const [d, setD] = useState<Brouillon>({
    service: moi.service ?? '', site: moi.site ?? '', telephone: moi.telephone, numero_or: '', date_besoin: null,
    piece_technique: false, equipement_designation: '', equipement_marque: '', equipement_modele: '',
    equipement_serie: '', activite: '', activite_autre: '', urgence: 2, justification_urgence: '',
    lignes: [ligneVide()],
  })
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    Promise.all([
      api<Page<Site>>('/sites/?actif=true'), api<Page<Service>>('/services/?actif=true'), api<Page<Unite>>('/unites/'),
      id ? api<Demande>(`/achats/demandes/${id}/`) : null,
    ])
      .then(([si, se, un, existante]) => {
        setSites(si.results)
        setServices(se.results)
        setUnites(un.results)
        if (existante) setD(existante)
      })
      .catch((e: Error) => setErreur(e.message))
  }, [id])

  const champ = <K extends keyof Brouillon>(k: K, v: Brouillon[K]) => setD((x) => ({ ...x, [k]: v }))
  const ligne = (i: number, k: keyof Ligne, v: string | number) =>
    setD((x) => ({ ...x, lignes: x.lignes.map((l, j) => (j === i ? { ...l, [k]: v } : l)) }))

  async function enregistrer(e: FormEvent) {
    e.preventDefault()
    setEnCours(true)
    setErreur('')
    try {
      const corps = JSON.stringify({ ...d, date_besoin: d.date_besoin || null })
      const r = await api<Demande>(id ? `/achats/demandes/${id}/` : '/achats/demandes/', { method: id ? 'PUT' : 'POST', body: corps })
      location.hash = `#/demandes/${r.id}`
    } catch (err) {
      setErreur((err as Error).message)
      setEnCours(false)
    }
  }

  return (
    <form className="fiche" onSubmit={enregistrer}>
      <h2>{id ? 'Modifier la demande' : "Nouvelle demande d'achat"}</h2>

      <fieldset>
        <legend>1. Demandeur</legend>
        <div className="grille">
          <label>Service / Direction
            <select required value={d.service} onChange={(e) => champ('service', Number(e.target.value))}>
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
          <label>Téléphone
            <input value={d.telephone} onChange={(e) => champ('telephone', e.target.value)} />
          </label>
          <label>Numéro OR
            <input value={d.numero_or} onChange={(e) => champ('numero_or', e.target.value)} />
          </label>
          <label>Date de besoin souhaitée
            <input type="date" value={d.date_besoin ?? ''} onChange={(e) => champ('date_besoin', e.target.value)} />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend>2. Équipement concerné</legend>
        <label className="case">
          <input type="checkbox" checked={d.piece_technique} onChange={(e) => champ('piece_technique', e.target.checked)} />
          Pièces techniques (équipement et photo obligatoires)
        </label>
        <div className="grille">
          <label>Désignation de l'équipement
            <input required={d.piece_technique} value={d.equipement_designation} onChange={(e) => champ('equipement_designation', e.target.value)} />
          </label>
          <label>Marque
            <input value={d.equipement_marque} onChange={(e) => champ('equipement_marque', e.target.value)} />
          </label>
          <label>Modèle
            <input value={d.equipement_modele} onChange={(e) => champ('equipement_modele', e.target.value)} />
          </label>
          <label>N° de série / immatriculation
            <input required={d.piece_technique} value={d.equipement_serie} onChange={(e) => champ('equipement_serie', e.target.value)} />
          </label>
          <label>Activité
            <select value={d.activite} onChange={(e) => champ('activite', e.target.value)}>
              <option value="">—</option>
              <option value="MANUTENTION">Manutention</option>
              <option value="LEVAGE">Levage</option>
              <option value="TRANSPORT">Transport</option>
              <option value="AUTRE">Autre</option>
            </select>
          </label>
          {d.activite === 'AUTRE' && (
            <label>Préciser
              <input value={d.activite_autre} onChange={(e) => champ('activite_autre', e.target.value)} />
            </label>
          )}
        </div>
        <p className="aide">La photo de la pièce ou de la plaque signalétique s'ajoute après l'enregistrement.</p>
      </fieldset>

      <fieldset>
        <legend>3. Articles demandés</legend>
        {d.lignes.map((l, i) => (
          <div className="ligne" key={i}>
            <label>Désignation
              <input required value={l.designation} onChange={(e) => ligne(i, 'designation', e.target.value)} />
            </label>
            <label>Référence constructeur / n° de pièce
              <input value={l.reference_constructeur} onChange={(e) => ligne(i, 'reference_constructeur', e.target.value)} />
            </label>
            <label>Qté
              <input required type="number" min="0.01" step="0.01" value={l.quantite} onChange={(e) => ligne(i, 'quantite', e.target.value)} />
            </label>
            <label>Unité
              <select required value={l.unite} onChange={(e) => ligne(i, 'unite', Number(e.target.value))}>
                <option value="">…</option>
                {unites.map((u) => <option key={u.id} value={u.id}>{u.code}</option>)}
              </select>
            </label>
            <label>Observations
              <input value={l.observations} onChange={(e) => ligne(i, 'observations', e.target.value)} />
            </label>
            {d.lignes.length > 1 && (
              <button type="button" className="discret" onClick={() => champ('lignes', d.lignes.filter((_, j) => j !== i))}>
                Retirer
              </button>
            )}
          </div>
        ))}
        <button type="button" className="secondaire" onClick={() => champ('lignes', [...d.lignes, ligneVide()])}>
          Ajouter un article
        </button>
      </fieldset>

      <fieldset>
        <legend>4. Niveau d'urgence</legend>
        {[
          [1, 'Urgent', "Machine ou activité à l'arrêt. Bon de commande sous 4 h ouvrées."],
          [2, 'Normal', 'Besoin courant. Bon de commande sous 2 jours ouvrés.'],
          [3, 'Planifié', 'Maintenance préventive, réapprovisionnement. Bon de commande sous 3 jours ouvrés.'],
        ].map(([v, nom, aide]) => (
          <label className="case" key={v}>
            <input type="radio" name="urgence" checked={d.urgence === v} onChange={() => champ('urgence', v as number)} />
            <span><strong>{nom}</strong> : {aide}</span>
          </label>
        ))}
        {d.urgence === 1 && (
          <label>Justification de l'urgence (validation du Directeur Technique requise)
            <textarea required value={d.justification_urgence} onChange={(e) => champ('justification_urgence', e.target.value)} />
          </label>
        )}
      </fieldset>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      <div className="actions">
        <button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Enregistrer le brouillon'}</button>
        <a href={id ? `#/demandes/${id}` : '#/'}>Annuler</a>
      </div>
    </form>
  )
}
