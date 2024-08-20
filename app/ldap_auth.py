
import ldap3

class LdapAuth(object):
    def __init__(self, host, username, password, base, group):
        self.base = base
        self.host = host
        self.username = username
        self.password = password
        self.group = group
        self.searchScope = ldap3.SUBTREE
        self.attributes = ['displayName']
        self.dereference = ldap3.DEREF_ALWAYS

    def connect(self):
        try:
            #conn.protocol_version = ldap.VERSION3
            #ldap3.set_option(ldap.OPT_REFERRALS, 0)
            #ldap3.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
            self.conn = ldap3.Connection(self.host, self.username, self.password, auto_bind=True, auto_referrals=False)
            # except        ldap.INVALID_CREDENTIALS:
            #        return "Invalid credentials"
            # except        ldap.SERVER_DOWN:
            #        return "Server down"
            #baseDN = 'OU=ULK_Users,OU=ULK,OU=HZS,DC=hzscr,DC=cz'
            #searchScope = ldap3.SUBTREE
            #dereference = ldap3.DEREF_ALWAYS
            #attributes = ['employeeID', 'jpegPhoto', 'thumbnailPhoto']
            # only no locked users
            #searchFilter = '(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2))(!(lockoutTime=0))(!(objectClass=computer)))'
            #conn.search(baseDN, searchFilter, searchScope, dereference, attributes)
#    data = json.loads(conn.response_to_json())
#    entries = data["entries"]
            #self.l = ldap3.open(self.host)
            #self.l.protocol_version = ldap3.VERSION3
            #self.l.set_option(ldap3.OPT_REFERRALS, 0)
            #self.l.simple_bind_s(self.username, self.password)
        except ldap3.LDAPExeption as e:
            print (e)

    def userExist(self, oec):
        self.connect()
        self.oec = oec
        try:
            searchFilter = '(&(objectClass=user)(!(userAccountControl:1.2.840.113556.1.4.803:=2))(!(objectClass=computer))(sAMAccountName=%s))' % self.oec
            self.conn.search(self.base, searchFilter, self.searchScope, self.dereference, self.attributes)
            if self.conn.entries:
                for result in self.conn.entries:
                    self.result_dn = result.entry_dn
                    self.result_attrs = result.displayName.value
                    return (True)
            else:
                return
        except Exception as e:
            print (e)
            self.unbind()

    def checkPassword(self, passwd):
        try:
            self.conn = ldap3.Connection(self.host, self.result_dn, passwd, auto_bind=False, auto_referrals=False)
            if self.conn.bind():
                return True
            else:
                return False
        except ldap3.INVALID_CREDENTIALS:
                # Name or password were bad. Fail.
                print ("INVALID_CREDENTIALS")
                return False
        except ldap3.LDAPError as error_message:
            print ("LDAP Connect Fail: %s") % error_message

    def checkRights(self):
        try:
            self.connect()
            attributes = ["member"]
            searchFilter = "(objectClass=group)"
            self.conn.search(self.group, searchFilter, self.searchScope, self.dereference, attributes)
            if self.conn.entries:
                for result in self.conn.entries:
                    for member in result.member.values:
                        searchFilter = f'(distinguishedName={member})'
                        attributes = ['sAMAccountName']
                        self.conn.search(self.base, searchFilter, self.searchScope, self.dereference, attributes)
                        if self.conn.entries[0].sAMAccountName.values[0] == self.oec:
                            return (True)
        except Exception as e:
            print (e)
            self.unbind()

    def getDisplayName(self):
        return self.result_attrs

    def unbind(self):
        self.conn.unbind()
