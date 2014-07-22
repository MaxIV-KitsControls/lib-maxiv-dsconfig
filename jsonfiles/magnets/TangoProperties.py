TANGO_PROPERTIES = {
    'Magnet' : [
        {                                                 #Properties deduced from lattice or filled later
            'Tilt':0,
            #'IsCircuit':[''], 
            #''Sisters':[], 
            'Type':[''], 
        },     
        {
            'tilt':'Tilt',
            'l':'Length',                                 #Property read direct from lattice
             #'k1':'DYNAMIC_PROPERTIES:k1=float(XXX)',      #This becomes an attribute for kquad
             #'angle':'DYNAMIC_PROPERTIES:angle=float(XXX)' #This becomes an attribute for dipole
        }         
        ],
    'VAYAGScreen' : [
        {},    
        {
            'filename':'image'
        }   
        ]                    

    }
