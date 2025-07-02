import csv
import os
import socket
import dns.resolver
import whois
import tldextract


class DomainInfoScraper:
    def whois(self, domain):
        try:
            result = whois.whois(domain)

            if isinstance(result, dict):
                creation_date = result.get('creation_date')
                if isinstance(creation_date, list):
                    creation_date = creation_date[0]
                
                expiration_date = result.get('expiration_date')
                if isinstance(expiration_date, list):
                    expiration_date = expiration_date[0]

                updated_date = result.get('updated_date')
                if isinstance(updated_date, list):
                    updated_date = updated_date[0]

                emails = []
                # Ensure emails are added only if they exist and are not lists
                if result.get('emails'):
                    if isinstance(result.get('emails'), list):
                        emails.extend([e for e in result.get('emails') if e is not None])
                    else:
                        emails.append(result.get('emails'))
                if result.get('email'):
                    if isinstance(result.get('email'), list):
                        emails.extend([e for e in result.get('email') if e is not None])
                    else:
                        emails.append(result.get('email'))
                emails = [e for e in emails if e] # Filter out None or empty strings


                name_servers_raw = result.get('name_servers')
                if isinstance(name_servers_raw, list):
                    name_servers = ' / '.join([ns.strip('.') for ns in name_servers_raw if ns])
                elif name_servers_raw:
                    name_servers = name_servers_raw.strip('.')
                else:
                    name_servers = None

                registrar_raw = result.get('registrar')
                registrar = registrar_raw.split('(')[0].strip() if registrar_raw else None


                return {
                    'creation_date': creation_date,
                    'expiration_date': expiration_date,
                    'updated_date': updated_date,
                    'dnssec': result.get('dnssec'),
                    'emails': ' / '.join(list(set(emails))) if emails else None, # Use set to remove duplicates
                    'name_servers': name_servers,
                    'registrar': registrar,
                }
            else:
                # This handles cases where whois.whois returns a string error message or other non-dict types
                print(f"Whois Error: Unexpected result type for {domain}: {result}")
                return {}
        except Exception as e:
            print(f"Whois lookup failed for {domain}: {e}")
            return {}
    
    def getRegistrarInfo(self, name):
        # Source: https://www.icann.org/en/accredited-registrars
        filepath = 'data/Accredited-Registrars.csv'
        if not os.path.exists(filepath):
            print(f"File {filepath} does not exist.")
            return {}

        with open(filepath, mode='r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            if not name:
                return {}
            for row in reader:
                if row['Registrar Name'].lower() == name.lower():
                    return {
                        'registrar_country': row['Country/Territory'],
                    }
        return {}
    
    def get_A_DNS(self, domain):
        try:
            # Use tldextract to ensure we're querying the base domain
            extracted = tldextract.extract(domain)
            hostname = f"{extracted.domain}.{extracted.suffix}"
            _, _, ip_addresses = socket.gethostbyname_ex(hostname)
            return {'ip_addresses': ip_addresses}
        except Exception as e:
            print(f"DNS Error for {domain}: {e}")
            return {}
        
    def ip_in_range(self, ip, start, end):
        try:
            ip = int.from_bytes(socket.inet_aton(ip), 'big')
            start = int.from_bytes(socket.inet_aton(start), 'big')
            end = int.from_bytes(socket.inet_aton(end), 'big')
            return start <= ip <= end
        except OSError as e:
            print(f"IP range check error: {e} for IP {ip}")
            return False
        
    def get_ASN(self, ip):
        # Source: https://iptoasn.com
        filename = 'data/ip2asn-v4.tsv'
        if not os.path.exists(filename):
            print(f"File {filename} does not exist.")
            return {}

        with open(filename, 'r', encoding='utf-8') as file:
            reader = csv.reader(file, delimiter='\t')
            for row in reader:
                if len(row) >= 5 and self.ip_in_range(ip, row[0], row[1]):
                    return {
                        'ASN': row[2],
                        'ASN_Country': row[3],
                        'ASN_Description': row[4],
                    }
        return {}
    
    def get_TXT_records(self, domain):
        TXT = []
        SPF = []
        try:
            answers = dns.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                for txt_string in rdata.strings:
                    decoded_txt = txt_string.decode('utf-8')
                    TXT.append(decoded_txt)
                    if 'v=spf1' in decoded_txt:
                        SPF.append(decoded_txt)
        except dns.resolver.NoAnswer:
            # No TXT records found
            pass
        except dns.resolver.NXDOMAIN:
            # Domain does not exist
            pass
        except Exception as e:
            print(f"TXT record error for {domain}: {e}")
        return {'TXT': TXT, 'SPF': SPF}
    
    def get_MX_records(self, domain):
        MX = []
        try:
            answers = dns.resolver.resolve(domain, 'MX')
            for rdata in answers:
                MX.append(str(rdata.exchange).rstrip('.')) # Remove trailing dot
        except dns.resolver.NoAnswer:
            # No MX records found
            pass
        except dns.resolver.NXDOMAIN:
            # Domain does not exist
            pass
        except Exception as e:
            print(f"MX record error for {domain}: {e}")
        return {'MX': MX}
    
    def get_MX_info(self, mx_record):
        mx_record = mx_record.strip('.')
        # Keep the full mx_record, especially if it's a subdomain of a large provider
        # The original logic '.'.join(mx_record.split('.')[-2:]) might cut off too much
        # if the record is something like mx.google.com. rather than just google.com.

        try:
            ip_address = socket.gethostbyname(mx_record)
        except socket.gaierror as e:
            print(f"MX IP lookup failed for {mx_record}: {e}")
            return {}
        except Exception as e:
            print(f"MX IP lookup unexpected error for {mx_record}: {e}")
            return {}

        asn_info = self.get_ASN(ip_address)
        return {
            'MX_IP': ip_address,
            'MX_ASN#': asn_info.get('ASN'),
            'MX_ASN_Country': asn_info.get('ASN_Country'),
            'MX_ASN_Description': asn_info.get('ASN_Description'),
        }

    def get_nameservers(self, domain):
        try:
            ns = dns.resolver.resolve(domain, 'NS')
            return [str(rdata.target).rstrip('.') for rdata in ns]
        except dns.resolver.NoAnswer:
            pass
        except dns.resolver.NXDOMAIN:
            pass
        except Exception as e:
            print(f"NS Error for {domain}: {e}")
        return []

    def perform_test(self, domain):
        # Always extract the base domain for WHOIS and DNS lookups
        extracted = tldextract.extract(domain)
        base_domain = f"{extracted.domain}.{extracted.suffix}"
        
        result = {'domain': base_domain}
        
        # WHOIS Information
        whois_info = self.whois(base_domain)
        if whois_info: # Check if whois_info is not empty
            result.update(whois_info)
            # Registrar Info depends on WHOIS registrar
            registrar_info = self.getRegistrarInfo(whois_info.get('registrar'))
            result.update(registrar_info)
        else:
            print(f"Warning: No WHOIS data retrieved for {base_domain}")
            # Initialize WHOIS-related fields to None to avoid KeyError later if not present
            result.update({
                'creation_date': None, 'expiration_date': None, 'updated_date': None,
                'dnssec': None, 'emails': None, 'name_servers': None, 'registrar': None,
                'registrar_country': None
            })

        # A DNS (IP Addresses)
        ip_addresses_data = self.get_A_DNS(base_domain)
        result.update(ip_addresses_data)

        if 'ip_addresses' in result and result['ip_addresses']:
            # Take the first IP for ASN lookup
            asn = self.get_ASN(result['ip_addresses'][0])
            result.update(asn)
        else:
            # Initialize ASN-related fields if no IP addresses
            result.update({'ASN': None, 'ASN_Country': None, 'ASN_Description': None})

        # TXT Records (including SPF)
        txt_spf_data = self.get_TXT_records(base_domain)
        result.update(txt_spf_data)

        # MX Records and MX Info
        mx_records_data = self.get_MX_records(base_domain)
        result['MX'] = ' / '.join(mx_records_data['MX']) if mx_records_data['MX'] else None
        
        if mx_records_data['MX']:
            mx_info = self.get_MX_info(mx_records_data['MX'][0])
            result.update(mx_info)
        else:
            # Initialize MX-related fields if no MX records
            result.update({'MX_IP': None, 'MX_ASN#': None, 'MX_ASN_Country': None, 'MX_ASN_Description': None})

        # Format lists into strings for CSV output
        result['ip_addresses'] = ' / '.join(result['ip_addresses']) if 'ip_addresses' in result and isinstance(result['ip_addresses'], (list, tuple)) else result.get('ip_addresses')
        result['TXT'] = ' / '.join(result['TXT']) if 'TXT' in result and isinstance(result['TXT'], list) else result.get('TXT')
        result['SPF'] = ' / '.join(result['SPF']) if 'SPF' in result and isinstance(result['SPF'], list) else result.get('SPF')
        
        # Ensure name_servers is properly formatted, prioritizing whois_info if available
        if not result.get('name_servers'):
            name_servers_from_dns = self.get_nameservers(base_domain)
            result['name_servers'] = ' / '.join(name_servers_from_dns) if name_servers_from_dns else None
        
        return result