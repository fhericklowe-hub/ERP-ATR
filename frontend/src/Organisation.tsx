import { type FormEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from './api'

type Site = { id: number; code: string; nom: string; ville: string; adresse: string; est_siege: boolean; actif: boolean }
type Service = { id: number; code: string; nom: string; responsable: number | null; responsable_nom: string; actif: boolean }
type Personne = { id: number; username: string; first_name: string; last_name: string }
type SaisieSite = Omit<Site, 'id'> & { id?: number }
type SaisieService = Omit<Service, 'id' | 'responsable_nom'> & { id?: number }

const SITE_VIDE: SaisieSite = { code: '', nom: '', ville: '', adresse: '', est_siege: false, actif: true }
const SERVICE_VIDE: SaisieService = { code: '', nom: '', responsable: null, actif: true }

/** L'organisation : les sites, les services, et le responsable qui valide les demandes de chaque service. */
export default function Organisation() {
  const [sites, setSites] = useState<Site[]>([])
  const [services, setServices] = useState<Service[]>([])
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [site, setSite] = useState<SaisieSite | null>(null)
  const [service, setService] = useState<SaisieService | null>(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api<Page<Site>>('/sites/?page_size=200').then((p) => setSites(p.results)).catch((e: Error) => setErreur(e.message))
    api<Page<Service>>('/services/?page_size=200').then((p) => setServices(p.results)).catch((e: Error) => setErreur(e.message))
  }, [])
  useEffect(charger, [charger])
  useEffect(() => {
    api<Page<Personne>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
  }, [])

  async function enregistrer(e: FormEvent, chemin: string, saisie: { id?: number }, fermer: () => void) {
    e.preventDefault()
    setErreur('')
    try {
      const { id, ...corps } = saisie
      await api(id ? `${chemin}${id}/` : chemin, { method: id ? 'PATCH' : 'POST', body: JSON.stringify(corps) })
      fermer()
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
  }
  const sansResponsable = services.filter((s) => s.actif && !s.responsable).length

  return (
    <>
      <div className="barre"><h2>Sites et services</h2></div>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      <section aria-label="Services">
        <div className="barre">
          <h3>Services</h3>
          {!service && <div className="actions"><button onClick={() => { setErreur(''); setService(SERVICE_VIDE) }}>Nouveau service</button></div>}
        </div>
        <p className="aide">Le responsable d'un service valide les demandes d'achat et les demandes de sortie de stock de ce service.</p>
        {sansResponsable > 0 && <p className="erreur">{sansResponsable} service{sansResponsable > 1 ? 's actifs n\'ont' : ' actif n\'a'} pas de responsable : les demandes correspondantes ne pourront pas être envoyées en validation.</p>}
        {service && (
          <form className="fiche" onSubmit={(e) => enregistrer(e, '/services/', service, () => setService(null))}>
            <fieldset>
              <legend>{service.id ? `Service ${service.nom}` : 'Nouveau service'}</legend>
              <div className="grille">
                <label>Code<input required maxLength={10} value={service.code} onChange={(e) => setService({ ...service, code: e.target.value })} /></label>
                <label>Nom<input required maxLength={100} value={service.nom} onChange={(e) => setService({ ...service, nom: e.target.value })} /></label>
                <label>Responsable
                  <select value={service.responsable ?? ''} onChange={(e) => setService({ ...service, responsable: Number(e.target.value) || null })}>
                    <option value="">Aucun</option>
                    {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
                  </select>
                </label>
              </div>
              {service.id && <label className="case"><input type="checkbox" checked={service.actif} onChange={(e) => setService({ ...service, actif: e.target.checked })} /> Actif (décoché : n'est plus proposé dans les listes)</label>}
              <div className="actions">
                <button type="button" className="secondaire" onClick={() => { setService(null); setErreur('') }}>Annuler</button>
                <button>Enregistrer le service</button>
              </div>
            </fieldset>
          </form>
        )}
        <div className="defilant">
          <table>
            <thead><tr><th>Code</th><th>Nom</th><th>Responsable</th><th></th></tr></thead>
            <tbody>
              {services.map((s) => (
                <tr key={s.id}>
                  <td>{s.code}</td><td>{s.nom}{!s.actif && <> <span className="pastille">Désactivé</span></>}</td>
                  <td>{s.responsable_nom || <span className="aide">Aucun</span>}</td>
                  <td><button className="secondaire" onClick={() => { setErreur(''); setService({ id: s.id, code: s.code, nom: s.nom, responsable: s.responsable, actif: s.actif }) }}>Modifier</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-label="Sites">
        <div className="barre">
          <h3>Sites</h3>
          {!site && <div className="actions"><button onClick={() => { setErreur(''); setSite(SITE_VIDE) }}>Nouveau site</button></div>}
        </div>
        {site && (
          <form className="fiche" onSubmit={(e) => enregistrer(e, '/sites/', site, () => setSite(null))}>
            <fieldset>
              <legend>{site.id ? `Site ${site.nom}` : 'Nouveau site'}</legend>
              <div className="grille">
                <label>Code<input required maxLength={10} value={site.code} onChange={(e) => setSite({ ...site, code: e.target.value })} /></label>
                <label>Nom<input required maxLength={100} value={site.nom} onChange={(e) => setSite({ ...site, nom: e.target.value })} /></label>
                <label>Ville<input maxLength={100} value={site.ville} onChange={(e) => setSite({ ...site, ville: e.target.value })} /></label>
              </div>
              <label>Adresse<textarea rows={2} value={site.adresse} onChange={(e) => setSite({ ...site, adresse: e.target.value })} /></label>
              <label className="case"><input type="checkbox" checked={site.est_siege} onChange={(e) => setSite({ ...site, est_siege: e.target.checked })} /> Siège de l'entreprise</label>
              {site.id && <label className="case"><input type="checkbox" checked={site.actif} onChange={(e) => setSite({ ...site, actif: e.target.checked })} /> Actif (décoché : n'est plus proposé dans les listes)</label>}
              <div className="actions">
                <button type="button" className="secondaire" onClick={() => { setSite(null); setErreur('') }}>Annuler</button>
                <button>Enregistrer le site</button>
              </div>
            </fieldset>
          </form>
        )}
        <div className="defilant">
          <table>
            <thead><tr><th>Code</th><th>Nom</th><th>Ville</th><th></th></tr></thead>
            <tbody>
              {sites.map((s) => (
                <tr key={s.id}>
                  <td>{s.code}</td>
                  <td>{s.nom}{s.est_siege && <> <span className="pastille complete">Siège</span></>}{!s.actif && <> <span className="pastille">Désactivé</span></>}</td>
                  <td>{s.ville}</td>
                  <td><button className="secondaire" onClick={() => { setErreur(''); setSite({ id: s.id, code: s.code, nom: s.nom, ville: s.ville, adresse: s.adresse, est_siege: s.est_siege, actif: s.actif }) }}>Modifier</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="aide">Les magasins de stock de chaque site se règlent encore dans l'administration.</p>
      </section>
    </>
  )
}
