===============
Database Schema
===============

These are the schema of the tables in the backend database.  The databsae code is all in the ``db`` submodule of ``snappl``.  Normally, you will not interact with these directly.  Rather, you will call ``snappl`` library functions that contact the web API frontend to the database.  You only really need to know about these if you're working on the backend.

Last updated 2025-10-17.

.. contents::



**Table:** ``provenance``
-------------------------


Data product provenance

=============== =========== ===== ======== ===============================================================
Column          Type        null? Default  Comment                                                        
=============== =========== ===== ======== ===============================================================
``id``          ``uuid``    NO    ``None`` Unique hash of the provenance                                  
``environment`` ``integer`` YES   ``None`` Environment; see snpit_utils.provenance.Provenance.environments
``env_major``   ``integer`` YES   ``None`` Semantic major version of environment for this provenance      
``env_minor``   ``integer`` YES   ``None`` Semantic minor version of environment for this provenance      
``process``     ``text``    NO    ``None`` Name of the process or code associated with this provenace     
``major``       ``integer`` NO    ``None`` Semantic major version of code for this provenance             
``minor``       ``integer`` NO    ``None`` Semantic minor version of code for this provenance             
``params``      ``jsonb``   YES   ``None`` Parameters that define the process behavior for this provenance
=============== =========== ===== ======== ===============================================================


**Table:** ``provenance_upstream``
----------------------------------


Upstream linkage table for provenance

================= ======== ===== ======== =======
Column            Type     null? Default  Comment
================= ======== ===== ======== =======
``downstream_id`` ``uuid`` NO    ``None`` None   
``upstream_id``   ``uuid`` NO    ``None`` None   
================= ======== ===== ======== =======


**Table:** ``provenance_tag``
-----------------------------


Human readable tags for collections of provenances

================= ======== ===== ======== ======================================================================
Column            Type     null? Default  Comment                                                               
================= ======== ===== ======== ======================================================================
``tag``           ``text`` NO    ``None`` Human-readable tag                                                    
``process``       ``text`` NO    ``None`` process of the provenance; must match corresponding provenance process
``provenance_id`` ``uuid`` NO    ``None`` id of the provenance                                                  
================= ======== ===== ======== ======================================================================


**Table:** ``l2image``
----------------------


L2 image

================= ==================== ===== =============== ===========================================
Column            Type                 null? Default         Comment                                    
================= ==================== ===== =============== ===========================================
``id``            ``uuid``             NO    ``None``        None                                       
``provenance_id`` ``uuid``             NO    ``None``        None                                       
``pointing``      ``integer``          YES   ``None``        Pointing of the exposure this image is from
``sca``           ``integer``          YES   ``None``        SCA of this image                          
``filter``        ``text``             NO    ``None``        None                                       
``ra``            ``double precision`` NO    ``None``        None                                       
``dec``           ``double precision`` NO    ``None``        None                                       
``ra_corner_00``  ``real``             NO    ``None``        RA of pixel (0,0)                          
``ra_corner_01``  ``real``             NO    ``None``        RA of pixel (0,height-1)                   
``ra_corner_10``  ``real``             NO    ``None``        RA of pixel (width-1,0)                    
``ra_corner_11``  ``real``             NO    ``None``        RA of pixel (width-1,height-1)             
``dec_corner_00`` ``real``             NO    ``None``        Dec of pixel (0,0)                         
``dec_corner_01`` ``real``             NO    ``None``        Dec of pixel (0,height-1)                  
``dec_corner_10`` ``real``             NO    ``None``        Dec of pixel (width-1,0)                   
``dec_corner_11`` ``real``             NO    ``None``        Dec of pixel (width-1,height-1)            
``filepath``      ``text``             NO    ``None``        None                                       
``extension``     ``ARRAY``            YES   ``None``        None                                       
``width``         ``smallint``         YES   ``None``        None                                       
``height``        ``smallint``         YES   ``None``        None                                       
``format``        ``smallint``         NO    ``0``           0=Unknown, 1=FITS, 2=Roman Datamodel       
``mjd_start``     ``double precision`` NO    ``None``        None                                       
``exptime``       ``real``             NO    ``None``        None                                       
``properties``    ``jsonb``            YES   ``'{}'::jsonb`` None                                       
================= ==================== ===== =============== ===========================================


**Table:** ``summed_image``
---------------------------


image that is a sum of L2 images

================= ==================== ===== ======== =======
Column            Type                 null? Default  Comment
================= ==================== ===== ======== =======
``id``            ``uuid``             NO    ``None`` None   
``provenance_id`` ``uuid``             NO    ``None`` None   
``filter``        ``text``             NO    ``None`` None   
``ra``            ``double precision`` NO    ``None`` None   
``dec``           ``double precision`` NO    ``None`` None   
``ra_corner_00``  ``real``             NO    ``None`` None   
``ra_corner_01``  ``real``             NO    ``None`` None   
``ra_corner_10``  ``real``             NO    ``None`` None   
``ra_corner_11``  ``real``             NO    ``None`` None   
``dec_corner_00`` ``real``             NO    ``None`` None   
``dec_corner_01`` ``real``             NO    ``None`` None   
``dec_corner_10`` ``real``             NO    ``None`` None   
``dec_corner_11`` ``real``             NO    ``None`` None   
``filepath``      ``text``             NO    ``None`` None   
``extension``     ``ARRAY``            YES   ``None`` None   
``width``         ``smallint``         YES   ``None`` None   
``height``        ``smallint``         YES   ``None`` None   
``format``        ``smallint``         NO    ``None`` None   
``mjd_start``     ``double precision`` NO    ``None`` None   
``mjd_end``       ``double precision`` NO    ``None`` None   
``properties``    ``jsonb``            YES   ``None`` None   
================= ==================== ===== ======== =======


**Table:** ``summed_image_component``
-------------------------------------


summed_image linkage table

=================== ======== ===== ======== =======
Column              Type     null? Default  Comment
=================== ======== ===== ======== =======
``summed_image_id`` ``uuid`` NO    ``None`` None   
``l2image_id``      ``uuid`` NO    ``None`` None   
=================== ======== ===== ======== =======


**Table:** ``diaobject``
------------------------


Known transients or simulated transients

================= ==================== ===== ======== ==========================================================
Column            Type                 null? Default  Comment                                                   
================= ==================== ===== ======== ==========================================================
``id``            ``uuid``             NO    ``None`` None                                                      
``provenance_id`` ``uuid``             NO    ``None`` None                                                      
``name``          ``text``             YES   ``None`` Name or id of the transient within its provenance.        
``iauname``       ``text``             YES   ``None`` IAU/TNS name of the transient.                            
``ra``            ``double precision`` YES   ``None`` Approx (±1"ish) RA of object; ICRS decimal degrees        
``dec``           ``double precision`` YES   ``None`` Approx (±1"ish) Dec of object; ICRS decimal degrees       
``mjd_discovery`` ``double precision`` YES   ``None`` MJD of image where the transient was discovered           
``mjd_peak``      ``double precision`` YES   ``None`` Approx. MJD where transient is at peak flux               
``mjd_start``     ``double precision`` YES   ``None`` Approx. MJD where the transient lightcurve "starts"       
``mjd_end``       ``double precision`` YES   ``None`` Approx. MJD where the transient lightcurve "ends"         
``properties``    ``jsonb``            YES   ``None`` Collection-specific additional properties of the transient
``ndetected``     ``integer``          NO    ``1``    None                                                      
================= ==================== ===== ======== ==========================================================


**Table:** ``diaobject_position``
---------------------------------


Calculated positions for a diaobject

================= ============================ ===== ========= =========================================
Column            Type                         null? Default   Comment                                  
================= ============================ ===== ========= =========================================
``id``            ``uuid``                     NO    ``None``  None                                     
``diaobject_id``  ``uuid``                     NO    ``None``  None                                     
``provenance_id`` ``uuid``                     NO    ``None``  None                                     
``ra``            ``double precision``         YES   ``None``  RA in ICRS decimal degrees               
``ra_err``        ``double precision``         YES   ``None``  Uncertainty on RA                        
``dec``           ``double precision``         YES   ``None``  Dec in ICRS decimal degrees              
``dec_err``       ``double precision``         YES   ``None``  Uncertainty on Dec                       
``ra_dec_covar``  ``double precision``         YES   ``None``  Covariance between RA and Dec            
``calculated_at`` ``timestamp with time zone`` YES   ``now()`` Time when this position was calculculated
================= ============================ ===== ========= =========================================


**Table:** ``lightcurve``
-------------------------


Transient object light curves; (provenance_id,diaobject_id,filter) is unique

================= ============================ ===== ========= =======
Column            Type                         null? Default   Comment
================= ============================ ===== ========= =======
``id``            ``uuid``                     NO    ``None``  None   
``provenance_id`` ``uuid``                     NO    ``None``  None   
``diaobject_id``  ``uuid``                     NO    ``None``  None   
``filter``        ``text``                     NO    ``None``  None   
``filepath``      ``text``                     NO    ``None``  None   
``created_at``    ``timestamp with time zone`` YES   ``now()`` None   
================= ============================ ===== ========= =======


**Table:** ``authuser``
-----------------------


Users

=============== ========= ===== ===================== ============================================
Column          Type      null? Default               Comment                                     
=============== ========= ===== ===================== ============================================
``id``          ``uuid``  NO    ``gen_random_uuid()`` None                                        
``username``    ``text``  NO    ``None``              None                                        
``displayname`` ``text``  NO    ``None``              None                                        
``email``       ``text``  NO    ``None``              None                                        
``pubkey``      ``text``  YES   ``None``              RSA public key                              
``privkey``     ``jsonb`` YES   ``None``              RSA private key encrypted with user password
=============== ========= ===== ===================== ============================================


**Table:** ``passwordlink``
---------------------------


(no description)

=========== ============================ ===== ======== =======
Column      Type                         null? Default  Comment
=========== ============================ ===== ======== =======
``id``      ``uuid``                     NO    ``None`` None   
``userid``  ``uuid``                     NO    ``None`` None   
``expires`` ``timestamp with time zone`` YES   ``None`` None   
=========== ============================ ===== ======== =======

