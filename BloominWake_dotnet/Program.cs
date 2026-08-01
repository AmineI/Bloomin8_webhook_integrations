using System.Globalization;
using Windows.Devices.Bluetooth;
using Windows.Devices.Bluetooth.Advertisement;
using Windows.Devices.Bluetooth.GenericAttributeProfile;
using Windows.Storage.Streams;

namespace BleWake;

internal static class Program
{
    // ─── Bloomin8 BLE constants ────────────────────────────────────
    private static readonly Guid ServiceUuid = Guid.Parse("0000f000-0000-1000-8000-00805f9b34fb");
    private static readonly Guid CharUuid    = Guid.Parse("0000f001-0000-1000-8000-00805f9b34fb");
    private static readonly byte[][] WakePayloads = [[0x01], [0x00]];
    // ───────────────────────────────────────────────────────────────

    private static async Task<int> Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("Usage: BleWake <MAC address>");
            Console.Error.WriteLine("  e.g. BleWake AA:BB:CC:DD:EE:FF");
            return 1;
        }

        var mac = args[0];
        if (!TryParseMac(mac, out var macUint64))
        {
            Console.Error.WriteLine($"Invalid MAC address: {mac}");
            return 1;
        }

        return await WakeDevice(mac, macUint64);
    }

    private static async Task<int> WakeDevice(string macDisplay, ulong macAddress)
    {
        // 1 ── Discover and connect
        Console.WriteLine($"Scanning for {macDisplay} ...");

        var addressType = await FindAddressType(macAddress, TimeSpan.FromSeconds(15));
        if (addressType is null)
        {
            Console.Error.WriteLine("No advertisement received from that address within 15 seconds.");
            Console.Error.WriteLine("Confirm the frame is advertising, then try pairing it in Windows Bluetooth settings.");
            return 1;
        }

        Console.WriteLine($"  Found advertisement ({addressType})");
        Console.WriteLine($"Connecting to {macDisplay} ...");

        using var device = await BluetoothLEDevice.FromBluetoothAddressAsync(macAddress, addressType.Value);
        if (device is null)
        {
            Console.Error.WriteLine("Windows saw the advertisement but could not create a BLE connection.");
            Console.Error.WriteLine("Remove and re-pair the frame in Windows Bluetooth settings, then try again.");
            return 1;
        }

        Console.WriteLine($"  Connected: {device.Name}");

        // 2 ── Discover the wake service
        var svcResult = await device.GetGattServicesForUuidAsync(ServiceUuid, BluetoothCacheMode.Uncached);
        if (svcResult.Status != GattCommunicationStatus.Success || svcResult.Services.Count == 0)
        {
            Console.Error.WriteLine($"  Service {ServiceUuid} not found (status: {svcResult.Status}).");
            return 1;
        }

        Console.WriteLine("  Found wake service");

        // 3 ── Discover the wake characteristic
        var charResult = await svcResult.Services[0].GetCharacteristicsForUuidAsync(CharUuid);
        if (charResult.Status != GattCommunicationStatus.Success || charResult.Characteristics.Count == 0)
        {
            Console.Error.WriteLine($"  Characteristic {CharUuid} not found (status: {charResult.Status}).");
            return 1;
        }

        Console.WriteLine("  Found wake characteristic");

        // 4 ── Write and release the wake pulse
        for (var index = 0; index < WakePayloads.Length; index++)
        {
            using var writer = new DataWriter();
            writer.WriteBytes(WakePayloads[index]);

            var writeResult = await charResult.Characteristics[0].WriteValueAsync(
                writer.DetachBuffer(),
                GattWriteOption.WriteWithoutResponse);

            if (writeResult != GattCommunicationStatus.Success)
            {
                Console.Error.WriteLine($"  Write failed (status: {writeResult}).");
                return 1;
            }

            if (index == 0)
            {
                await Task.Delay(1);
            }
        }

        Console.WriteLine("  Wake pulse sent successfully!");
        return 0;
    }

    private static async Task<BluetoothAddressType?> FindAddressType(ulong macAddress, TimeSpan timeout)
    {
        var result = new TaskCompletionSource<BluetoothAddressType>(
            TaskCreationOptions.RunContinuationsAsynchronously);
        var watcher = new BluetoothLEAdvertisementWatcher
        {
            ScanningMode = BluetoothLEScanningMode.Active
        };

        void OnAdvertisementReceived(
            BluetoothLEAdvertisementWatcher sender,
            BluetoothLEAdvertisementReceivedEventArgs eventArgs)
        {
            if (eventArgs.BluetoothAddress == macAddress)
            {
                result.TrySetResult(eventArgs.BluetoothAddressType);
            }
        }

        watcher.Received += OnAdvertisementReceived;
        watcher.Start();

        try
        {
            var completedTask = await Task.WhenAny(result.Task, Task.Delay(timeout));
            return completedTask == result.Task ? await result.Task : null;
        }
        finally
        {
            watcher.Stop();
            watcher.Received -= OnAdvertisementReceived;
        }
    }

    private static bool TryParseMac(string mac, out ulong result)
    {
        var cleaned = mac.Replace(":", "").Replace("-", "");
        return ulong.TryParse(cleaned, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out result);
    }
}
