TANGO_PROPERTIES = {
    'VAMagnet' : [
        {                                                 #Properties deduced from lattice or filled later
            'energy':'', 
            'isCircuit':'', 
            'sisters':'',
            'type':''
        },     
        {
            'l':'length',                                 #Property read direct from lattice
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
